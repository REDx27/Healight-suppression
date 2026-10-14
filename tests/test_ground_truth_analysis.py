"""Integration tests for marked ground-truth measurement analysis."""

import csv
import json

import pytest

from glare_tracker.diagnostics import DiagnosticRecorder
from scripts.analyze_ground_truth import analyze_session, write_results


def _tracking_sample(recorder, eye_offset, light_x):
    recorder.record_tracking(
        eyes=(
            (-3.0 + eye_offset, -50.0, 9.0),
            (3.0 + eye_offset, -50.0, 11.0),
        ),
        sources=(("L1", (light_x, 200.0, 10.0), 0.9, "tracked"),),
        intersections=(
            ("L1/E1", (-2.0, 0.0, 9.2), True),
            ("L1/E2", (2.0, 0.0, 10.8), True),
        ),
    )


def test_analyzer_summarizes_driver_and_road_markers(tmp_path):
    recorder = DiagnosticRecorder()
    session_dir = recorder.start(tmp_path)
    recorder.record_ground_truth(
        "Driver Eye Midpoint", (0.0, -50.0, 10.0), label="driver-r1"
    )
    _tracking_sample(recorder, eye_offset=0.0, light_x=0.0)
    _tracking_sample(recorder, eye_offset=1.0, light_x=0.0)

    recorder.record_ground_truth(
        "Road Light", (0.0, 200.0, 10.0), label="lamp-r1"
    )
    _tracking_sample(recorder, eye_offset=0.0, light_x=1.0)
    recorder.stop()

    summaries = analyze_session(session_dir, window_seconds=10.0)

    assert len(summaries) == 2
    driver, lamp = summaries
    assert driver["condition_id"] == "driver-r1"
    assert driver["sample_count"] == 2
    assert driver["mean_estimate_x_cm"] == pytest.approx(0.5)
    assert driver["mean_3d_error_cm"] == pytest.approx(0.5)
    assert driver["rmse_3d_cm"] == pytest.approx(2 ** -0.5)
    assert lamp["condition_id"] == "lamp-r1"
    assert lamp["sample_count"] == 1
    assert lamp["mean_3d_error_cm"] == pytest.approx(1.0)

    csv_path, json_path = write_results(session_dir, summaries)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        output_rows = list(csv.DictReader(handle))
    output_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(output_rows) == 2
    assert output_rows[0]["status"] == "OK"
    assert len(output_json["conditions"]) == 2
