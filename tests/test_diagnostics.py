"""Regression coverage for timestamped telemetry and video recording."""

import csv
import json
import os
import time

import cv2
import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from glare_tracker.diagnostics import DiagnosticRecorder
from glare_tracker.operating_modes import OperatingMode, SessionState
from glare_tracker.window import MainWindow


def _read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_recorder_writes_timestamped_tracking_and_decodable_video(tmp_path):
    recorder = DiagnosticRecorder(video_fps=20.0)
    session_dir = recorder.start(
        tmp_path,
        metadata={"test_name": "diagnostics-regression", "camera_index": 0},
    )

    recorder.record_event("session_state", details={"state": "Run"})
    observed_at = time.time() - 0.01
    queued = recorder.record_tracking(
        eyes=((-3.1, -50.0, 9.5), (3.1, -50.0, 10.5)),
        sources=(("L1", (0.0, 200.0, 10.0), 0.91, "tracked"),),
        intersections=(
            ("L1/E1", (-2.48, 0.0, 9.6), True),
            ("L1/E2", (2.48, 0.0, 10.4), True),
        ),
        light_timestamps={"L1": observed_at},
    )
    assert queued
    assert recorder.record_ground_truth(
        "Driver Eye Midpoint", (0.0, -50.0, 10.0), label="driver-centre-r1"
    )

    for value in (20, 80, 140):
        frame = np.full((48, 64, 3), value, dtype=np.uint8)
        assert recorder.record_frame("driver", frame)
    recorder.stop()

    manifest = json.loads(
        (session_dir / "session.json").read_text(encoding="utf-8")
    )
    assert manifest["metadata"]["test_name"] == "diagnostics-regression"
    assert manifest["video_frames"] == {"driver": 3}
    assert manifest["dropped_video_frames"] == 0
    assert manifest["dropped_telemetry_rows"] == 0
    assert manifest["errors"] == []
    assert manifest["started_utc"].endswith("+00:00")
    assert manifest["stopped_utc"].endswith("+00:00")

    telemetry = _read_csv(session_dir / "telemetry.csv")
    tracking = [row for row in telemetry if row["event"] == "tracking_sample"]
    assert len(tracking) == 2
    assert {row["eye_id"] for row in tracking} == {"E1", "E2"}
    assert all(row["sample_id"] == tracking[0]["sample_id"] for row in tracking)
    assert all(int(row["monotonic_ns"]) > 0 for row in telemetry)
    assert all(row["utc_time"].endswith("+00:00") for row in telemetry)
    assert float(tracking[0]["light_age_ms"]) >= 0.0
    assert tracking[0]["intersection_x_cm"] == "-2.48"
    markers = [
        row for row in telemetry if row["event"] == "ground_truth_marker"
    ]
    assert len(markers) == 1
    assert markers[0]["ground_truth_target"] == "Driver Eye Midpoint"
    assert markers[0]["ground_truth_y_cm"] == "-50.0"
    assert markers[0]["message"] == "driver-centre-r1"

    video_rows = _read_csv(session_dir / "video_timestamps.csv")
    assert [int(row["frame_index"]) for row in video_rows] == [0, 1, 2]
    assert all(row["stream"] == "driver" for row in video_rows)
    assert all(int(row["monotonic_ns"]) > 0 for row in video_rows)

    capture = cv2.VideoCapture(str(session_dir / "driver.avi"))
    decoded = 0
    while True:
        ok, _ = capture.read()
        if not ok:
            break
        decoded += 1
    capture.release()
    assert decoded == 3


def test_recorder_rejects_non_rgb_uint8_frames(tmp_path):
    recorder = DiagnosticRecorder()
    recorder.start(tmp_path)
    with pytest.raises(ValueError, match="HxWx3 uint8 RGB"):
        recorder.record_frame("driver", np.zeros((10, 10), dtype=np.uint8))
    with pytest.raises(ValueError, match="HxWx3 uint8 RGB"):
        recorder.record_frame(
            "driver", np.zeros((10, 10, 3), dtype=np.float32)
        )
    recorder.stop()


def test_main_window_recording_control_captures_preview_and_geometry(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GLARETRACKER_DIAGNOSTICS_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.FULLY_MANUAL.value
    )

    window.controls.check_record_diagnostics.setChecked(True)
    assert window.diagnostics.is_active
    session_dir = window.diagnostics.session_dir
    assert str(session_dir) in window.controls.diagnostics_status.text()

    image = QImage(64, 48, QImage.Format_RGB888)
    image.fill(0x305070)
    window._update_driver_frame(image)
    window.controls.edit_ground_truth_label.setText("manual-centre-r1")
    window.controls.btn_mark_ground_truth.click()
    window._set_session_state(SessionState.RUN)
    app.processEvents()

    window.controls.check_record_diagnostics.setChecked(False)
    assert not window.diagnostics.is_active
    assert (session_dir / "driver.avi").exists()
    telemetry = _read_csv(session_dir / "telemetry.csv")
    assert any(row["event"] == "session_state" for row in telemetry)
    assert any(row["event"] == "tracking_sample" for row in telemetry)
    assert any(
        row["event"] == "ground_truth_marker"
        and row["message"] == "manual-centre-r1"
        for row in telemetry
    )
    window.close()
