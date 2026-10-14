"""Tests for timing analysis and stale-sample fail-safe behavior."""

import json
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from glare_tracker.diagnostics import DiagnosticRecorder
from glare_tracker.light_sources import TrackedLightSource
from glare_tracker.operating_modes import OperatingMode, SessionState
from glare_tracker.window import MainWindow
from scripts.analyze_latency import analyze_latency


def _acceptance(path, geometry_limit=50.0):
    path.write_text(
        json.dumps(
            {
                "minimum_complete_samples": 1,
                "max_p95_capture_to_geometry_ms": geometry_limit,
                "max_p95_capture_to_preview_ms": 60.0,
                "max_p95_stereo_readout_skew_ms": 10.0,
                "maximum_stale_rejections": 0,
            }
        ),
        encoding="utf-8",
    )


def test_latency_analyzer_merges_pipeline_stages_by_stream_and_frame(tmp_path):
    recorder = DiagnosticRecorder()
    session_dir = recorder.start(tmp_path)
    recorder.record_event(
        "pipeline_capture",
        details={
            "stream": "driver",
            "frame_index": 7,
            "capture_started_ns": 1_000_000,
            "capture_complete_ns": 3_000_000,
            "detection_complete_ns": 8_000_000,
            "gui_received_ns": 10_000_000,
        },
    )
    recorder.record_event(
        "pipeline_geometry",
        details={
            "stream": "driver",
            "frame_index": 7,
            "capture_complete_ns": 3_000_000,
            "geometry_complete_ns": 20_000_000,
        },
    )
    recorder.record_event(
        "pipeline_preview_queued",
        details={
            "stream": "driver",
            "frame_index": 7,
            "capture_complete_ns": 3_000_000,
            "preview_queued_ns": 23_000_000,
        },
    )
    recorder.stop()
    acceptance = tmp_path / "acceptance.json"
    _acceptance(acceptance)

    report = analyze_latency(session_dir, acceptance)

    assert report["status"] == "PASS"
    assert report["metrics"]["capture_read_ms"]["mean_ms"] == 2.0
    assert report["metrics"]["detection_ms"]["mean_ms"] == 5.0
    assert report["metrics"]["worker_to_gui_ms"]["mean_ms"] == 2.0
    assert report["metrics"]["capture_to_geometry_ms"]["p95_ms"] == 17.0
    assert report["metrics"]["capture_to_preview_ms"]["p95_ms"] == 20.0


def test_stale_eye_sample_is_rejected_and_clears_tracking(tmp_path, monkeypatch):
    monkeypatch.setenv("GLARETRACKER_DIAGNOSTICS_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.FULLY_MANUAL.value
    )
    window._set_session_state(SessionState.RUN)
    window.controls.check_record_diagnostics.setChecked(True)
    now_ns = time.monotonic_ns()
    window._latest_pipeline_timing["driver"] = {
        "stream": "driver",
        "frame_index": 1,
        "capture_complete_ns": now_ns - 1_000_000_000,
        "detection_complete_ns": now_ns - 900_000_000,
    }

    window._on_eyes_detected(-3, -50, 9, 3, -50, 11)

    assert window.tracker.last_eye_cm is None
    session_dir = window.diagnostics.session_dir
    window.controls.check_record_diagnostics.setChecked(False)
    telemetry = (session_dir / "telemetry.csv").read_text(encoding="utf-8")
    assert "stale_sample_rejected" in telemetry
    window.close()
    app.processEvents()


def test_stale_held_light_source_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GLARETRACKER_DIAGNOSTICS_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.DRIVER_FIXED.value
    )
    window._session_state = SessionState.RUN
    window.controls.check_record_diagnostics.setChecked(True)
    stale_source = TrackedLightSource(
        stable_id="L1",
        position=(0.0, 200.0, 10.0),
        timestamp=time.time() - 2.0,
        confidence=0.9,
        state="temporarily_lost",
        image_center=(320.0, 240.0),
        diameter_px=10.0,
    )

    window._on_auto_lights([stale_source])

    assert window.tracker._live_light_sources == ()
    assert not window._road_position_ready
    session_dir = window.diagnostics.session_dir
    window.controls.check_record_diagnostics.setChecked(False)
    telemetry = (session_dir / "telemetry.csv").read_text(encoding="utf-8")
    assert "stale_light_sources_rejected" in telemetry
    window.close()
    app.processEvents()
