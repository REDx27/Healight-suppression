"""Analyze measured end-to-end eye/light/windshield intersection trials."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np


def _point(trial, field):
    point = np.asarray(trial[field], dtype=np.float64)
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise ValueError(f"{trial.get('id', '<unknown>')} {field} must be finite XYZ")
    return point


def reference_intersection(eye_cm, light_cm):
    """Independent eye-to-light segment intersection with physical ``Y=0``."""

    eye = np.asarray(eye_cm, dtype=np.float64)
    light = np.asarray(light_cm, dtype=np.float64)
    depth_span = light[1] - eye[1]
    if abs(depth_span) < 1e-12:
        return None
    eye_weight = light[1] / depth_span
    light_weight = -eye[1] / depth_span
    if eye_weight < 0.0 or light_weight < 0.0:
        return None
    point = eye_weight * eye + light_weight * light
    point[1] = 0.0
    return point


def _planar_error(first, second):
    return float(np.linalg.norm((first - second)[[0, 2]]))


def _metrics(values):
    values = np.asarray(values, dtype=np.float64)
    return {
        "count": int(len(values)),
        "mean_cm": float(np.mean(values)),
        "rmse_cm": float(np.sqrt(np.mean(np.square(values)))),
        "p95_cm": float(np.percentile(values, 95)),
        "max_cm": float(np.max(values)),
    }


def analyze_trials(data):
    acceptance = data.get("acceptance", {})
    required = (
        "minimum_trials",
        "max_geometry_rmse_cm",
        "max_end_to_end_rmse_cm",
        "max_end_to_end_error_cm",
    )
    missing = [field for field in required if field not in acceptance]
    if missing:
        raise ValueError(
            "Acceptance limits must be declared before analysis: "
            + ", ".join(missing)
        )
    trials = data.get("trials", [])
    identifiers = [str(trial.get("id", "")) for trial in trials]
    if any(not identifier for identifier in identifiers):
        raise ValueError("Every trial requires a non-empty id")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Trial ids must be unique")
    if not trials:
        raise ValueError("At least one trial is required")

    results = []
    categories = {
        "eye_input_error_cm": [],
        "light_input_error_cm": [],
        "physical_mark_error_cm": [],
        "input_propagation_error_cm": [],
        "geometry_error_cm": [],
        "end_to_end_error_cm": [],
    }
    for trial in trials:
        measured_eye = _point(trial, "measured_eye_cm")
        estimated_eye = _point(trial, "estimated_eye_cm")
        measured_light = _point(trial, "measured_light_cm")
        estimated_light = _point(trial, "estimated_light_cm")
        physical = _point(trial, "physical_intersection_cm")
        application = _point(trial, "application_intersection_cm")
        if abs(physical[1]) > 0.5 or abs(application[1]) > 1e-6:
            raise ValueError(
                f"{trial['id']} intersections must lie on windshield Y=0"
            )

        reference = reference_intersection(measured_eye, measured_light)
        estimated_reference = reference_intersection(estimated_eye, estimated_light)
        if reference is None or estimated_reference is None:
            raise ValueError(f"{trial['id']} eye/light segment does not cross Y=0")

        row = {
            "id": trial["id"],
            "eye_id": trial.get("eye_id", ""),
            "light_id": trial.get("light_id", ""),
            "reference_x_cm": float(reference[0]),
            "reference_z_cm": float(reference[2]),
            "estimated_reference_x_cm": float(estimated_reference[0]),
            "estimated_reference_z_cm": float(estimated_reference[2]),
            "physical_x_cm": float(physical[0]),
            "physical_z_cm": float(physical[2]),
            "application_x_cm": float(application[0]),
            "application_z_cm": float(application[2]),
            "eye_input_error_cm": float(np.linalg.norm(estimated_eye - measured_eye)),
            "light_input_error_cm": float(
                np.linalg.norm(estimated_light - measured_light)
            ),
            "physical_mark_error_cm": _planar_error(physical, reference),
            "input_propagation_error_cm": _planar_error(
                estimated_reference, reference
            ),
            "geometry_error_cm": _planar_error(application, estimated_reference),
            "end_to_end_error_cm": _planar_error(application, physical),
        }
        results.append(row)
        for category in categories:
            categories[category].append(row[category])

    metrics = {name: _metrics(values) for name, values in categories.items()}
    checks = {
        "minimum_trials": len(results) >= int(acceptance["minimum_trials"]),
        "geometry_rmse_cm": (
            metrics["geometry_error_cm"]["rmse_cm"]
            <= float(acceptance["max_geometry_rmse_cm"])
        ),
        "end_to_end_rmse_cm": (
            metrics["end_to_end_error_cm"]["rmse_cm"]
            <= float(acceptance["max_end_to_end_rmse_cm"])
        ),
        "end_to_end_max_cm": (
            metrics["end_to_end_error_cm"]["max_cm"]
            <= float(acceptance["max_end_to_end_error_cm"])
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "acceptance": acceptance,
        "checks": checks,
        "metrics": metrics,
        "trials": results,
    }


def write_report(report, json_path: Path, csv_path: Path):
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    rows = report["trials"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze physical GlareTracker intersection trials"
    )
    parser.add_argument("input_json", type=Path)
    parser.add_argument(
        "--report-json",
        type=Path,
        default=Path("intersection_validation_report.json"),
    )
    parser.add_argument(
        "--report-csv",
        type=Path,
        default=Path("intersection_validation_trials.csv"),
    )
    args = parser.parse_args()
    data = json.loads(args.input_json.read_text(encoding="utf-8"))
    report = analyze_trials(data)
    write_report(report, args.report_json, args.report_csv)
    print(f"Physical intersection validation: {report['status']}")
    print(args.report_json)
    print(args.report_csv)
    raise SystemExit(0 if report["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
