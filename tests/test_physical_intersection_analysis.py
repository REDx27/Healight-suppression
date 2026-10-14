"""Tests for independent physical intersection error decomposition."""

import json

import pytest

from scripts.analyze_physical_intersections import (
    analyze_trials,
    reference_intersection,
    write_report,
)


def _data(application_x=0.0):
    return {
        "acceptance": {
            "minimum_trials": 1,
            "max_geometry_rmse_cm": 0.2,
            "max_end_to_end_rmse_cm": 0.5,
            "max_end_to_end_error_cm": 1.0,
        },
        "trials": [
            {
                "id": "T001",
                "eye_id": "E1",
                "light_id": "L1",
                "measured_eye_cm": [-3.0, -50.0, 10.0],
                "estimated_eye_cm": [-3.0, -50.0, 10.0],
                "measured_light_cm": [6.0, 100.0, 10.0],
                "estimated_light_cm": [6.0, 100.0, 10.0],
                "physical_intersection_cm": [0.0, 0.0, 10.0],
                "application_intersection_cm": [application_x, 0.0, 10.0],
            }
        ],
    }


def test_reference_intersection_is_independent_and_exact():
    assert reference_intersection((-3, -50, 8), (6, 100, 14)) == pytest.approx(
        (0.0, 0.0, 10.0)
    )
    assert reference_intersection((0, -50, 10), (1, -10, 10)) is None


def test_analysis_separates_geometry_and_end_to_end_errors(tmp_path):
    report = analyze_trials(_data(application_x=0.1))

    assert report["status"] == "PASS"
    assert report["metrics"]["eye_input_error_cm"]["max_cm"] == 0.0
    assert report["metrics"]["light_input_error_cm"]["max_cm"] == 0.0
    assert report["metrics"]["geometry_error_cm"]["rmse_cm"] == pytest.approx(
        0.1
    )
    assert report["metrics"]["end_to_end_error_cm"]["rmse_cm"] == pytest.approx(
        0.1
    )

    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "trials.csv"
    write_report(report, json_path, csv_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "PASS"
    assert csv_path.read_text(encoding="utf-8").startswith("id,eye_id,light_id")


def test_analysis_fails_predeclared_limits_without_hiding_results():
    report = analyze_trials(_data(application_x=2.0))
    assert report["status"] == "FAIL"
    assert report["checks"]["geometry_rmse_cm"] is False
    assert report["checks"]["end_to_end_max_cm"] is False


def test_analysis_requires_limits_and_valid_windshield_points():
    data = _data()
    del data["acceptance"]["minimum_trials"]
    with pytest.raises(ValueError, match="must be declared before"):
        analyze_trials(data)

    data = _data()
    data["trials"][0]["physical_intersection_cm"][1] = 2.0
    with pytest.raises(ValueError, match="must lie on windshield"):
        analyze_trials(data)
