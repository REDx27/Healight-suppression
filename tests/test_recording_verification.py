"""Regression coverage for the Stage 2 recording-soak verifier."""

import csv
import json

import numpy as np
import pytest

from glare_tracker.diagnostics import DiagnosticRecorder
from scripts.verify_recording_session import verify_recording_session


def _acceptance(path, **overrides):
    data = {
        "minimum_duration_s": 0,
        "expected_streams": ["driver", "road_primary"],
        "minimum_telemetry_rows": 2,
        "minimum_frames_per_stream": 2,
        "minimum_average_fps": {"driver": 0, "road_primary": 0},
        "maximum_frame_gap_ms": 60000,
        "maximum_stream_start_delay_ms": 60000,
        "maximum_stream_end_delay_ms": 60000,
        "maximum_dropped_video_frames": 0,
        "maximum_dropped_telemetry_rows": 0,
        "maximum_recording_errors": 0,
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _session(tmp_path):
    recorder = DiagnosticRecorder(video_fps=10)
    session = recorder.start(tmp_path / "sessions", metadata={"test": "soak-verifier"})
    recorder.record_event("session_state", details={"state": "Run"})
    for value in (20, 80):
        frame = np.full((24, 32, 3), value, np.uint8)
        recorder.record_frame("driver", frame)
        recorder.record_frame("road_primary", frame)
    recorder.stop()
    return session


def test_closed_multistream_recording_passes_strict_file_checks(tmp_path):
    session = _session(tmp_path)
    report = verify_recording_session(session, _acceptance(tmp_path / "acceptance.json"))

    assert report["status"] == "PASS"
    assert report["issues"] == []
    assert report["telemetry_rows"] >= 3
    assert report["streams"]["driver"]["decoded_frames"] == 2
    assert report["streams"]["road_primary"]["sidecar_frames"] == 2
    assert all(report["checks"].values())


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        ("drop", "dropped_video_frames"),
        ("error", "recording_errors"),
        ("duration", "minimum_duration"),
        ("missing_video", "stream_driver_video_exists"),
        ("count", "stream_driver_manifest_count"),
        ("stream", "expected_stream_set"),
    ],
)
def test_manifest_or_file_failures_produce_specific_failed_checks(
    tmp_path, mutation, failed_check,
):
    session = _session(tmp_path)
    acceptance = _acceptance(
        tmp_path / "acceptance.json",
        minimum_duration_s=999 if mutation == "duration" else 0,
    )
    manifest_path = session / "session.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "drop":
        manifest["dropped_video_frames"] = 1
    elif mutation == "error":
        manifest["errors"] = ["simulated writer failure"]
    elif mutation == "missing_video":
        (session / "driver.avi").unlink()
    elif mutation == "count":
        manifest["video_frames"]["driver"] = 99
    elif mutation == "stream":
        manifest["video_frames"]["unexpected"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = verify_recording_session(session, acceptance)
    assert report["status"] == "FAIL"
    assert report["checks"][failed_check] is False
    assert report["issues"]


def test_sidecar_frame_gaps_and_timestamp_reversal_fail(tmp_path):
    session = _session(tmp_path)
    sidecar = session / "video_timestamps.csv"
    with sidecar.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    driver_rows = [row for row in rows if row["stream"] == "driver"]
    driver_rows[1]["frame_index"] = "3"
    driver_rows[1]["monotonic_ns"] = str(int(driver_rows[0]["monotonic_ns"]) - 1)
    with sidecar.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    report = verify_recording_session(
        session, _acceptance(tmp_path / "acceptance.json"))
    assert report["status"] == "FAIL"
    assert not report["checks"]["stream_driver_contiguous_indices"]
    assert not report["checks"]["video_monotonic_order"]


def test_acceptance_must_be_complete_and_stream_specific(tmp_path):
    session = _session(tmp_path)
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_text(json.dumps({"minimum_duration_s": 600}), encoding="utf-8")
    with pytest.raises(ValueError, match="must be declared before"):
        verify_recording_session(session, acceptance)

    _acceptance(acceptance, minimum_average_fps={"driver": 5})
    with pytest.raises(ValueError, match="every expected stream exactly"):
        verify_recording_session(session, acceptance)
