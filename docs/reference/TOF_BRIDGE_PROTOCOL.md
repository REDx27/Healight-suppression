# GlareTracker ToF bridge v1

Status 2026-11-24: the Python host/parser/calibration workflow is implemented and
tested with generated packets. The purchased sensor has **no controller connected**.
Controller selection, firmware implementation/flashing, wiring and physical serial
validation remain outstanding. This document specifies the firmware interface; it
does not claim a tested firmware build is included.

Update 2026-11-27: the intended controller is **Arduino Nano or Uno**. Operator wiring
examples cover the classic ATmega328P Nano/Uno R3; confirm the actual board variant.
Controller selection does not complete firmware commissioning or physical validation.
See the [illustrated offline setup guide](../guides/TOF_SENSOR_OFFLINE_SETUP_GUIDE.md).

## Transport and identity

USB serial, 115200 baud, UTF-8 newline-delimited JSON objects, maximum 512 bytes per
line. Do not mix debug text into the stream. `device_id` must identify the physical
sensor/mount assembly consistently; COM number alone is insufficient. Firmware must
echo the fresh host `session` token in every response and reset its outgoing sequence
when accepting a new HELLO. Do not echo an old session after a controller reset.

Host request:

```json
{"type":"HELLO","version":1,"session":"fresh-host-token"}
```

Controller reply:

```json
{"type":"HELLO","version":1,"session":"fresh-host-token","device_id":"driver-tof-rig1"}
```

Host sends a clock request after HELLO and about every two seconds:

```json
{"type":"SYNC","session":"fresh-host-token","id":"host-request-token"}
```

Controller replies immediately, echoing `id`; `ms` is its current monotonic uptime:

```json
{"type":"SYNC","session":"fresh-host-token","id":"host-request-token","ms":12340}
```

The host uses the request/reply midpoint as the time offset and half the round trip
as uncertainty. It rejects a synchronization round trip over 40 ms. Firmware should
service incoming commands promptly even while ranging. Do not batch old measurements.

## Range packet

After synchronization, send approximately 20-30 readings per second, subject to the
actual sensor timing budget. Every completed measurement, including invalid ones,
advances `seq` and sends its true quality:

```json
{"type":"RANGE","session":"fresh-host-token","seq":1,"ms":12380,"mm":502,"valid":true,"status":0,"timeout":false,"budget_ms":33}
```

| Field | Required meaning |
|---|---|
| `seq` | Strictly increasing integer within this connection session |
| `ms` | MCU monotonic time at measurement completion, not USB printing time |
| `mm` | Measured distance in mm; null/invalid value for a failed return |
| `valid` | Explicit boolean; true only after the sensor's quality checks pass |
| `status` | Integer sensor range status; 0 for valid, preserve other error codes |
| `timeout` | Explicit boolean from the acquisition, not a constant false |
| `budget_ms` | Actual configured measurement duration/budget; 33 is an example |

Example failed acquisition:

```json
{"type":"RANGE","session":"fresh-host-token","seq":2,"ms":12420,"mm":null,"valid":false,"status":4,"timeout":false,"budget_ms":33}
```

Do not convert `RangeStatus != 0`, timeouts, or sentinel distances into plausible
numbers. A simple library call that omits status cannot support this contract.
The host never substitutes a fabricated distance.

## Host rejection and recovery

- Wrong session, duplicate/out-of-order sequence, decreasing uptime, unexpected sync,
  malformed JSON, excessive buffer backlog and oversized lines invalidate the stream.
- Valid range is strictly positive and below 2000 mm, status 0, valid true, timeout false.
- Conservative host age includes measurement budget and clock uncertainty and must be
  <= 100 ms. Acquisition time used for pairing is completion minus the full budget.
- Fusion requires matching saved device identity, <= 100 ms range age, and <= 50 ms
  camera/range skew including clock uncertainty. Latest invalid quality blocks reuse
  of an earlier good return. Disconnect clears buffered history.
- Reconnect manually after a controller reboot, uptime rollover, port change or serial
  failure. This development version does not promise automatic serial reconnection.

`pyserial>=3.5` is listed in requirements; it was installed in the active Python 3.13
development environment. In the current no-controller setup, skip ToF explicitly.

See the [operator guide](../guides/DRIVER_AND_INSTALLED_RIG_CALIBRATION_GUIDE.md)
for measured bias, mount offsets, working-region assumptions and validation.
