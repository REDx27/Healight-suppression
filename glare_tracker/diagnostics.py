"""Asynchronous, timestamped research diagnostics recording.

The recorder keeps disk I/O and video encoding off the Qt GUI thread.  Every
encoded video frame receives a sidecar CSV row because ordinary video container
timestamps are not sufficient for camera-skew and end-to-end latency analysis.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from queue import Full, Queue
from threading import Lock, Thread
import time
from typing import Any, Iterable, Mapping, Sequence

import cv2
import numpy as np


TELEMETRY_FIELDS = (
    "sequence",
    "utc_time",
    "unix_time_ns",
    "monotonic_ns",
    "event",
    "sample_id",
    "eye_id",
    "eye_x_cm",
    "eye_y_cm",
    "eye_z_cm",
    "light_id",
    "light_x_cm",
    "light_y_cm",
    "light_z_cm",
    "light_observed_unix_s",
    "light_age_ms",
    "light_confidence",
    "light_state",
    "intersection_x_cm",
    "intersection_y_cm",
    "intersection_z_cm",
    "in_bounds",
    "ground_truth_target",
    "ground_truth_x_cm",
    "ground_truth_y_cm",
    "ground_truth_z_cm",
    "message",
    "details_json",
)

VIDEO_TIMESTAMP_FIELDS = (
    "sequence",
    "utc_time",
    "unix_time_ns",
    "monotonic_ns",
    "stream",
    "frame_index",
    "width",
    "height",
    "video_file",
)


def _utc_iso(unix_time_ns: int) -> str:
    return datetime.fromtimestamp(
        unix_time_ns / 1_000_000_000, tz=timezone.utc
    ).isoformat(timespec="microseconds")


class DiagnosticRecorder:
    """Write telemetry CSV and MJPEG preview videos in a background thread."""

    def __init__(
        self,
        *,
        video_fps: float = 30.0,
        codec: str = "MJPG",
        queue_capacity: int = 512,
    ):
        if len(codec) != 4:
            raise ValueError("Video codec must contain exactly four characters")
        self.video_fps = float(video_fps)
        self.codec = codec
        self._queue: Queue = Queue(maxsize=max(8, int(queue_capacity)))
        self._lock = Lock()
        self._active = False
        self._sequence = 0
        self._sample_id = 0
        self._session_dir: Path | None = None
        self._thread: Thread | None = None
        self._telemetry_file = None
        self._video_timestamp_file = None
        self._telemetry_writer = None
        self._video_timestamp_writer = None
        self._video_writers: dict[str, cv2.VideoWriter] = {}
        self._video_sizes: dict[str, tuple[int, int]] = {}
        self._video_frames: dict[str, int] = {}
        self._errors: list[str] = []
        self._dropped_video_frames = 0
        self._dropped_telemetry_rows = 0
        self._manifest: dict[str, Any] = {}

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def session_dir(self) -> Path | None:
        return self._session_dir

    @property
    def errors(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._errors)

    def start(
        self,
        output_root: str | Path,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        """Start a unique diagnostics session and return its directory."""

        if self._active:
            raise RuntimeError("Diagnostics recording is already active")

        now = datetime.now(timezone.utc)
        root = Path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        base_name = now.strftime("%Y%m%dT%H%M%S_%fZ")
        session_dir = root / base_name
        suffix = 1
        while session_dir.exists():
            session_dir = root / f"{base_name}_{suffix}"
            suffix += 1
        session_dir.mkdir()

        self._session_dir = session_dir
        self._sequence = 0
        self._sample_id = 0
        self._errors = []
        self._dropped_video_frames = 0
        self._dropped_telemetry_rows = 0
        self._video_writers = {}
        self._video_sizes = {}
        self._video_frames = {}
        self._queue = Queue(maxsize=self._queue.maxsize)

        self._telemetry_file = (session_dir / "telemetry.csv").open(
            "w", newline="", encoding="utf-8"
        )
        self._video_timestamp_file = (
            session_dir / "video_timestamps.csv"
        ).open("w", newline="", encoding="utf-8")
        self._telemetry_writer = csv.DictWriter(
            self._telemetry_file, fieldnames=TELEMETRY_FIELDS
        )
        self._video_timestamp_writer = csv.DictWriter(
            self._video_timestamp_file, fieldnames=VIDEO_TIMESTAMP_FIELDS
        )
        self._telemetry_writer.writeheader()
        self._video_timestamp_writer.writeheader()

        self._manifest = {
            "format_version": 1,
            "started_utc": now.isoformat(timespec="microseconds"),
            "video_codec": self.codec,
            "nominal_video_fps": self.video_fps,
            "metadata": dict(metadata or {}),
        }
        self._write_manifest()

        self._active = True
        self._thread = Thread(
            target=self._writer_loop,
            name="GlareTrackerDiagnosticsWriter",
            daemon=True,
        )
        self._thread.start()
        self.record_event("recording_started", message=str(session_dir))
        return session_dir

    def stop(self) -> Path | None:
        """Flush queued records, close all files, and return the session path."""

        if not self._active:
            return self._session_dir

        self.record_event("recording_stopped")
        self._active = False
        self._queue.put(("stop", None))
        if self._thread is not None:
            self._thread.join(timeout=15.0)
            if self._thread.is_alive():
                self._append_error("Diagnostics writer did not stop within 15 seconds")

        for writer in self._video_writers.values():
            writer.release()
        self._video_writers.clear()

        if self._telemetry_file is not None:
            self._telemetry_file.flush()
            self._telemetry_file.close()
        if self._video_timestamp_file is not None:
            self._video_timestamp_file.flush()
            self._video_timestamp_file.close()

        self._manifest.update(
            {
                "stopped_utc": datetime.now(timezone.utc).isoformat(
                    timespec="microseconds"
                ),
                "video_frames": dict(self._video_frames),
                "dropped_video_frames": self._dropped_video_frames,
                "dropped_telemetry_rows": self._dropped_telemetry_rows,
                "errors": list(self.errors),
            }
        )
        self._write_manifest()
        return self._session_dir

    def record_event(
        self,
        event: str,
        *,
        message: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> bool:
        """Queue a timestamped non-geometric event."""

        if not self._active:
            return False
        timestamp = self._timestamp()
        row = self._blank_telemetry_row(timestamp, event)
        row["message"] = message
        row["details_json"] = json.dumps(
            dict(details or {}), sort_keys=True, separators=(",", ":")
        )
        return self._queue_telemetry(row)

    def record_ground_truth(
        self,
        target: str,
        position_cm: Sequence[float],
        *,
        label: str = "",
    ) -> bool:
        """Mark the start of a measured, stationary ground-truth interval."""

        if not self._active:
            return False
        if len(position_cm) != 3:
            raise ValueError("Ground-truth position must contain X, Y, and Z")
        timestamp = self._timestamp()
        row = self._blank_telemetry_row(timestamp, "ground_truth_marker")
        row.update(
            {
                "ground_truth_target": str(target),
                "ground_truth_x_cm": position_cm[0],
                "ground_truth_y_cm": position_cm[1],
                "ground_truth_z_cm": position_cm[2],
                "message": label,
            }
        )
        return self._queue_telemetry(row)

    def record_tracking(
        self,
        eyes: Sequence[Sequence[float]],
        sources: Sequence[tuple[str, Sequence[float], float | None, str]],
        intersections: Sequence[tuple[str, Sequence[float] | None, bool]],
        *,
        light_timestamps: Mapping[str, float] | None = None,
    ) -> bool:
        """Queue one consistently timestamped row per eye/light intersection."""

        if not self._active:
            return False
        timestamp = self._timestamp()
        with self._lock:
            self._sample_id += 1
            sample_id = self._sample_id

        timestamp_map = dict(light_timestamps or {})
        any_queued = False
        intersection_index = 0
        for light_id, position, confidence, state in sources:
            observed_at = timestamp_map.get(light_id)
            light_age_ms = (
                max(0.0, timestamp[1] / 1_000_000_000 - observed_at) * 1000.0
                if observed_at is not None
                else ""
            )
            for eye_index, eye in enumerate(eyes, start=1):
                label, intersection, in_bounds = intersections[intersection_index]
                intersection_index += 1
                row = self._blank_telemetry_row(timestamp, "tracking_sample")
                row.update(
                    {
                        "sample_id": sample_id,
                        "eye_id": f"E{eye_index}",
                        "eye_x_cm": eye[0],
                        "eye_y_cm": eye[1],
                        "eye_z_cm": eye[2],
                        "light_id": light_id,
                        "light_x_cm": position[0],
                        "light_y_cm": position[1],
                        "light_z_cm": position[2],
                        "light_observed_unix_s": observed_at or "",
                        "light_age_ms": light_age_ms,
                        "light_confidence": (
                            "" if confidence is None else confidence
                        ),
                        "light_state": state,
                        "in_bounds": int(bool(in_bounds)),
                        "message": label,
                    }
                )
                if intersection is not None:
                    row.update(
                        {
                            "intersection_x_cm": intersection[0],
                            "intersection_y_cm": intersection[1],
                            "intersection_z_cm": intersection[2],
                        }
                    )
                any_queued = self._queue_telemetry(row) or any_queued
        return any_queued

    def record_frame(self, stream: str, frame_rgb: np.ndarray) -> bool:
        """Queue an RGB frame for MJPEG encoding and timestamp sidecar output."""

        if not self._active:
            return False
        frame = np.asarray(frame_rgb)
        if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
            raise ValueError("Video frames must be HxWx3 uint8 RGB arrays")
        timestamp = self._timestamp()
        item = ("frame", (str(stream), frame.copy(), timestamp))
        try:
            self._queue.put_nowait(item)
            return True
        except Full:
            with self._lock:
                self._dropped_video_frames += 1
            return False

    def _queue_telemetry(self, row: dict[str, Any]) -> bool:
        try:
            self._queue.put(("telemetry", row), timeout=0.25)
            return True
        except Full:
            with self._lock:
                self._dropped_telemetry_rows += 1
            return False

    def _writer_loop(self):
        while True:
            kind, payload = self._queue.get()
            try:
                if kind == "stop":
                    return
                if kind == "telemetry":
                    self._telemetry_writer.writerow(payload)
                elif kind == "frame":
                    self._write_video_frame(*payload)
            except Exception as error:  # recording must not crash the application
                self._append_error(f"{kind}: {error}")
            finally:
                self._queue.task_done()

    def _write_video_frame(
        self,
        stream: str,
        frame_rgb: np.ndarray,
        timestamp: tuple[int, int, int],
    ):
        safe_stream = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in stream
        ) or "camera"
        height, width = frame_rgb.shape[:2]
        writer = self._video_writers.get(safe_stream)
        if writer is None:
            video_path = self._session_dir / f"{safe_stream}.avi"
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*self.codec),
                self.video_fps,
                (width, height),
            )
            if not writer.isOpened():
                writer.release()
                raise RuntimeError(f"Could not open video writer for {video_path}")
            self._video_writers[safe_stream] = writer
            self._video_sizes[safe_stream] = (width, height)
            self._video_frames[safe_stream] = 0

        target_size = self._video_sizes[safe_stream]
        if (width, height) != target_size:
            frame_rgb = cv2.resize(frame_rgb, target_size)
            width, height = target_size

        writer.write(cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
        frame_index = self._video_frames[safe_stream]
        self._video_frames[safe_stream] += 1
        unix_time_ns, monotonic_ns, sequence = timestamp
        self._video_timestamp_writer.writerow(
            {
                "sequence": sequence,
                "utc_time": _utc_iso(unix_time_ns),
                "unix_time_ns": unix_time_ns,
                "monotonic_ns": monotonic_ns,
                "stream": safe_stream,
                "frame_index": frame_index,
                "width": width,
                "height": height,
                "video_file": f"{safe_stream}.avi",
            }
        )

    def _timestamp(self) -> tuple[int, int, int]:
        unix_time_ns = time.time_ns()
        monotonic_ns = time.monotonic_ns()
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        return unix_time_ns, monotonic_ns, sequence

    @staticmethod
    def _blank_telemetry_row(
        timestamp: tuple[int, int, int], event: str
    ) -> dict[str, Any]:
        unix_time_ns, monotonic_ns, sequence = timestamp
        row = {field: "" for field in TELEMETRY_FIELDS}
        row.update(
            {
                "sequence": sequence,
                "utc_time": _utc_iso(unix_time_ns),
                "unix_time_ns": unix_time_ns,
                "monotonic_ns": monotonic_ns,
                "event": event,
            }
        )
        return row

    def _append_error(self, message: str):
        with self._lock:
            self._errors.append(str(message))

    def _write_manifest(self):
        if self._session_dir is None:
            return
        (self._session_dir / "session.json").write_text(
            json.dumps(self._manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
