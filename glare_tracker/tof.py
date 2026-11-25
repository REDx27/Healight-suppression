"""Optional, bounded USB serial transport for a VL53L0X controller bridge."""

from collections import deque
import json
import time
import uuid

from PyQt5.QtCore import QThread, pyqtSignal


class RangeProtocol:
    """Reject old/reset streams and timestamp MCU samples in host monotonic time."""

    def __init__(self, session):
        self.session = session
        self.device_id = None
        self.sequence = -1
        self.last_ms = -1
        self.offset_ns = None
        self.uncertainty_ns = None
        self.requests = {}

    def sync_request(self, now_ns):
        key = str(now_ns)
        self.requests = {key: now_ns}
        return {"type": "SYNC", "session": self.session, "id": key}

    def feed(self, line, now_ns):
        if len(line) > 512:
            raise ValueError("Oversize sensor packet")
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError("Sensor packet must be a JSON object")
        if data.get("session") != self.session:
            raise ValueError("Wrong sensor session; reconnect after controller reset")
        kind = data.get("type")
        if kind == "HELLO":
            if (type(data.get("version")) is not int or data["version"] != 1
                    or not isinstance(data.get("device_id"), str) or not data["device_id"].strip()):
                raise ValueError("Unsupported sensor bridge")
            identity = str(data["device_id"])
            if self.device_id is not None and identity != self.device_id:
                raise ValueError("Sensor identity changed; reconnect")
            self.device_id = identity
            return None
        if not self.device_id:
            raise ValueError("Waiting for sensor HELLO")
        if kind == "SYNC":
            if type(data.get("ms")) is not int or data["ms"] < 0:
                raise ValueError("Sensor uptime must be a nonnegative integer")
            started = self.requests.pop(str(data.get("id")), None)
            if started is None:
                raise ValueError("Unrequested clock synchronization")
            uncertainty = (now_ns - started) // 2
            if not 0 <= uncertainty <= 20_000_000:
                raise ValueError("Sensor clock uncertainty exceeds 20 ms")
            self.offset_ns = (now_ns + started) // 2 - int(data["ms"]) * 1_000_000
            self.uncertainty_ns = uncertainty
            return None
        if kind != "RANGE" or self.offset_ns is None:
            raise ValueError("Waiting for synchronized RANGE data")
        if any(type(data.get(key)) is not int for key in ("seq", "ms", "budget_ms")):
            raise ValueError("Sensor sequence, uptime and timing budget must be integers")
        seq, ms = int(data["seq"]), int(data["ms"])
        if seq < 0 or ms < 0 or seq <= self.sequence or ms <= self.last_ms:
            raise ValueError("Duplicate, old or reset sensor observation")
        self.sequence, self.last_ms = seq, ms
        measured_ns = self.offset_ns + ms * 1_000_000
        # Timestamp denotes measurement completion; include the entire budget
        # conservatively rather than pretending receipt equals acquisition.
        budget_ns = int(data.get("budget_ms", 33)) * 1_000_000
        age_ns = now_ns - measured_ns + budget_ns + self.uncertainty_ns
        raw = data.get("mm")
        valid = (data.get("valid") is True and type(data.get("status")) is int and data["status"] == 0
                 and data.get("timeout") is False and isinstance(raw, (int, float))
                 and not isinstance(raw, bool) and 0 < raw < 2000
                 and 0 < budget_ns <= 100_000_000
                 and -self.uncertainty_ns <= now_ns - measured_ns
                 and age_ns <= 100_000_000)
        return {"device_id": self.device_id, "seq": seq, "valid": valid,
                "raw_cm": float(raw) / 10 if valid else None,
                "observed_ns": measured_ns - budget_ns,
                "received_ns": now_ns, "uncertainty_ns": self.uncertainty_ns,
                "reason": "valid" if valid else "invalid status, range or timing"}


class ToFSerialWorker(QThread):
    sample = pyqtSignal(object)
    status = pyqtSignal(str)

    def __init__(self, port, parent=None):
        super().__init__(parent)
        self.port = port
        self.latest = None
        self.history = deque(maxlen=40)

    def run(self):
        connection = None
        try:
            import serial
            connection = serial.Serial(self.port, 115200, timeout=0.1, write_timeout=0.2)
            session = uuid.uuid4().hex
            protocol = RangeProtocol(session)
            connection.reset_input_buffer()
            last_hello = last_sync = 0.
            buffer = bytearray()
            self.status.emit("Connecting: waiting for controller HELLO / clock sync")
            while not self.isInterruptionRequested():
                now = time.monotonic()
                if not protocol.device_id and now - last_hello > 1:
                    connection.write((json.dumps({"type": "HELLO", "version": 1,
                                                   "session": session}) + "\n").encode())
                    last_hello = now
                if protocol.device_id and now - last_sync > 2:
                    message = protocol.sync_request(time.monotonic_ns())
                    connection.write((json.dumps(message) + "\n").encode())
                    last_sync = now
                # read(256) can wait a whole serial timeout for a short SYNC
                # reply and make an otherwise healthy clock appear too slow.
                chunk = connection.read(max(1, min(connection.in_waiting, 512)))
                buffer.extend(chunk)
                if len(buffer) > 2048:
                    buffer.clear()
                    self.latest = None
                    self.history.clear()
                    self.status.emit("Rejected excessive serial backlog")
                while b"\n" in buffer:
                    line, _, remaining = buffer.partition(b"\n")
                    buffer = bytearray(remaining)
                    try:
                        result = protocol.feed(line, time.monotonic_ns())
                    except (ValueError, TypeError, KeyError, UnicodeError) as error:
                        self.latest = None
                        self.history.clear()
                        self.status.emit(str(error))
                        continue
                    if result is not None:
                        self.latest = result
                        if not result["valid"]:
                            self.history.clear()
                        self.history.append(result)
                        self.sample.emit(result)
                        self.status.emit("Receiving valid range" if result["valid"] else result["reason"])
        except Exception as error:
            self.status.emit(f"ToF unavailable: {error}")
        finally:
            self.latest = None
            self.history.clear()
            if connection is not None:
                connection.close()

    def stop(self):
        self.requestInterruption()
        return self.wait(1500) if self.isRunning() else True


def eligible_range(history, captured_ns, device_id):
    now = time.monotonic_ns()
    samples = tuple(history)
    # An invalid latest return is a quality barrier, not permission to reuse
    # an older face/target range from before the failure.
    if not samples or not samples[-1]["valid"]:
        return None
    candidates = [s for s in samples if s["valid"] and s["device_id"] == device_id
                  and 0 <= now - s["observed_ns"] <= 100_000_000
                  and abs(captured_ns - s["observed_ns"]) + s["uncertainty_ns"] <= 50_000_000]
    return min(candidates, key=lambda s: abs(captured_ns - s["observed_ns"])) if candidates else None
