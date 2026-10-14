"""Summarize measured ground-truth intervals from a diagnostics session.

Usage:
    py -3.13 scripts/analyze_ground_truth.py diagnostics/<session-directory>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable


TARGET_DRIVER = "Driver Eye Midpoint"
TARGET_LIGHT = "Road Light"
TARGET_INTERSECTION = "Windshield Intersection"


def _number(row, field):
    value = row.get(field, "")
    return None if value in (None, "") else float(value)


def _percentile(values: list[float], percentage: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _mean_position(points: Iterable[tuple[float, float, float]]):
    points = list(points)
    return tuple(fmean(point[axis] for point in points) for axis in range(3))


def _sample_positions(rows, target, light_id=None):
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("event") != "tracking_sample" or not row.get("sample_id"):
            continue
        grouped.setdefault(row["sample_id"], []).append(row)

    samples = []
    for sample_rows in grouped.values():
        if target == TARGET_DRIVER:
            unique_eyes = {}
            for row in sample_rows:
                coordinates = tuple(
                    _number(row, field)
                    for field in ("eye_x_cm", "eye_y_cm", "eye_z_cm")
                )
                if None not in coordinates:
                    unique_eyes[row["eye_id"]] = coordinates
            if unique_eyes:
                samples.append(_mean_position(unique_eyes.values()))
        elif target == TARGET_LIGHT:
            unique_lights = {}
            for row in sample_rows:
                if light_id and row.get("light_id") != light_id:
                    continue
                coordinates = tuple(
                    _number(row, field)
                    for field in ("light_x_cm", "light_y_cm", "light_z_cm")
                )
                if None not in coordinates:
                    unique_lights[row["light_id"]] = coordinates
            if len(unique_lights) == 1:
                samples.append(next(iter(unique_lights.values())))
        elif target == TARGET_INTERSECTION:
            intersections = []
            for row in sample_rows:
                coordinates = tuple(
                    _number(row, field)
                    for field in (
                        "intersection_x_cm",
                        "intersection_y_cm",
                        "intersection_z_cm",
                    )
                )
                if None not in coordinates and row.get("in_bounds") == "1":
                    intersections.append(coordinates)
            if intersections:
                samples.append(_mean_position(intersections))
    return samples


def analyze_session(session_dir: Path, window_seconds: float, light_id=None):
    telemetry_path = session_dir / "telemetry.csv"
    if not telemetry_path.exists():
        raise FileNotFoundError(f"Missing {telemetry_path}")
    with telemetry_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    markers = [row for row in rows if row.get("event") == "ground_truth_marker"]
    summaries = []
    window_ns = int(window_seconds * 1_000_000_000)
    for marker_index, marker in enumerate(markers, start=1):
        start_ns = int(marker["monotonic_ns"])
        end_ns = start_ns + window_ns
        later_markers = [
            int(candidate["monotonic_ns"])
            for candidate in markers
            if int(candidate["monotonic_ns"]) > start_ns
        ]
        if later_markers:
            end_ns = min(end_ns, min(later_markers))

        interval_rows = [
            row
            for row in rows
            if row.get("monotonic_ns")
            and start_ns <= int(row["monotonic_ns"]) < end_ns
        ]
        target = marker["ground_truth_target"]
        truth = (
            float(marker["ground_truth_x_cm"]),
            float(marker["ground_truth_y_cm"]),
            float(marker["ground_truth_z_cm"]),
        )
        samples = _sample_positions(interval_rows, target, light_id=light_id)
        summary = {
            "marker_index": marker_index,
            "condition_id": marker.get("message", ""),
            "target": target,
            "start_monotonic_ns": start_ns,
            "window_seconds": (end_ns - start_ns) / 1_000_000_000,
            "ground_truth_x_cm": truth[0],
            "ground_truth_y_cm": truth[1],
            "ground_truth_z_cm": truth[2],
            "sample_count": len(samples),
            "status": "OK" if samples else "NO_TRACKING_SAMPLES",
        }
        if samples:
            mean_position = _mean_position(samples)
            errors = [
                math.dist(sample, truth)
                for sample in samples
            ]
            summary.update(
                {
                    "mean_estimate_x_cm": mean_position[0],
                    "mean_estimate_y_cm": mean_position[1],
                    "mean_estimate_z_cm": mean_position[2],
                    "bias_x_cm": mean_position[0] - truth[0],
                    "bias_y_cm": mean_position[1] - truth[1],
                    "bias_z_cm": mean_position[2] - truth[2],
                    "mean_3d_error_cm": fmean(errors),
                    "rmse_3d_cm": math.sqrt(fmean(error * error for error in errors)),
                    "p95_3d_error_cm": _percentile(errors, 95.0),
                    "max_3d_error_cm": max(errors),
                    "jitter_x_std_cm": pstdev(point[0] for point in samples),
                    "jitter_y_std_cm": pstdev(point[1] for point in samples),
                    "jitter_z_std_cm": pstdev(point[2] for point in samples),
                }
            )
        summaries.append(summary)
    return summaries


def write_results(session_dir: Path, summaries):
    json_path = session_dir / "ground_truth_summary.json"
    csv_path = session_dir / "ground_truth_summary.csv"
    json_path.write_text(
        json.dumps({"conditions": summaries}, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    fieldnames = [
        "marker_index",
        "condition_id",
        "target",
        "start_monotonic_ns",
        "window_seconds",
        "ground_truth_x_cm",
        "ground_truth_y_cm",
        "ground_truth_z_cm",
        "sample_count",
        "status",
        "mean_estimate_x_cm",
        "mean_estimate_y_cm",
        "mean_estimate_z_cm",
        "bias_x_cm",
        "bias_y_cm",
        "bias_z_cm",
        "mean_3d_error_cm",
        "rmse_3d_cm",
        "p95_3d_error_cm",
        "max_3d_error_cm",
        "jitter_x_std_cm",
        "jitter_y_std_cm",
        "jitter_z_std_cm",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for summary in summaries:
            writer.writerow(summary)
    return csv_path, json_path


def main():
    parser = argparse.ArgumentParser(
        description="Analyze ground-truth markers in a GlareTracker session"
    )
    parser.add_argument("session_dir", type=Path)
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=10.0,
        help="Maximum measurement duration following each marker (default: 10)",
    )
    parser.add_argument(
        "--light-id",
        help="Analyze only one stable source ID when multiple lights are present",
    )
    args = parser.parse_args()
    if args.window_seconds <= 0:
        parser.error("--window-seconds must be positive")

    summaries = analyze_session(
        args.session_dir, args.window_seconds, light_id=args.light_id
    )
    csv_path, json_path = write_results(args.session_dir, summaries)
    print(f"Analyzed {len(summaries)} ground-truth interval(s)")
    print(csv_path)
    print(json_path)


if __name__ == "__main__":
    main()
