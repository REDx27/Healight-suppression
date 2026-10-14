"""Analyze instrumented pipeline timing and stale-sample rejection events."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def _distribution(values):
    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        return {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "count": int(len(array)),
        "mean_ms": float(np.mean(array)),
        "p50_ms": float(np.percentile(array, 50)),
        "p95_ms": float(np.percentile(array, 95)),
        "max_ms": float(np.max(array)),
    }


def analyze_latency(session_dir: Path, acceptance_path: Path):
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    required = (
        "minimum_complete_samples",
        "max_p95_capture_to_geometry_ms",
        "max_p95_capture_to_preview_ms",
        "max_p95_stereo_readout_skew_ms",
        "maximum_stale_rejections",
    )
    missing = [field for field in required if field not in acceptance]
    if missing:
        raise ValueError(
            "Latency acceptance limits must be declared before analysis: "
            + ", ".join(missing)
        )
    with (session_dir / "telemetry.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))

    frames = {}
    stale_rejections = 0
    for row in rows:
        event = row.get("event")
        if event == "stale_sample_rejected":
            stale_rejections += 1
            continue
        if event not in {
            "pipeline_capture",
            "pipeline_geometry",
            "pipeline_preview_queued",
        }:
            continue
        details = json.loads(row.get("details_json") or "{}")
        stream = details.get("stream")
        frame_index = details.get("frame_index")
        if stream is None or frame_index is None:
            continue
        frames.setdefault((str(stream), int(frame_index)), {}).update(details)

    metric_values = {
        "capture_read_ms": [],
        "detection_ms": [],
        "worker_to_gui_ms": [],
        "capture_to_geometry_ms": [],
        "capture_to_preview_ms": [],
        "stereo_readout_skew_ms": [],
    }
    frame_rows = []
    for (stream, frame_index), timing in sorted(frames.items()):
        output = {"stream": stream, "frame_index": frame_index}

        def duration(name, start_key, end_key):
            start = timing.get(start_key)
            end = timing.get(end_key)
            if start is None or end is None:
                output[name] = None
                return
            value = (int(end) - int(start)) / 1_000_000.0
            output[name] = value
            metric_values[name].append(value)

        duration("capture_read_ms", "capture_started_ns", "capture_complete_ns")
        duration("detection_ms", "capture_complete_ns", "detection_complete_ns")
        duration("worker_to_gui_ms", "detection_complete_ns", "gui_received_ns")
        duration(
            "capture_to_geometry_ms",
            "capture_complete_ns",
            "geometry_complete_ns",
        )
        duration(
            "capture_to_preview_ms",
            "capture_complete_ns",
            "preview_queued_ns",
        )
        if timing.get("readout_completion_skew_ns") is not None:
            value = abs(int(timing["readout_completion_skew_ns"])) / 1_000_000.0
            output["stereo_readout_skew_ms"] = value
            metric_values["stereo_readout_skew_ms"].append(value)
        else:
            output["stereo_readout_skew_ms"] = None
        frame_rows.append(output)

    metrics = {name: _distribution(values) for name, values in metric_values.items()}
    complete_samples = metrics["capture_to_geometry_ms"]["count"]

    def within(metric, limit):
        value = metrics[metric]["p95_ms"]
        return value is not None and value <= float(limit)

    stereo_count = metrics["stereo_readout_skew_ms"]["count"]
    stereo_check = (
        True
        if stereo_count == 0
        else within(
            "stereo_readout_skew_ms",
            acceptance["max_p95_stereo_readout_skew_ms"],
        )
    )
    checks = {
        "minimum_complete_samples": (
            complete_samples >= int(acceptance["minimum_complete_samples"])
        ),
        "capture_to_geometry_p95": within(
            "capture_to_geometry_ms",
            acceptance["max_p95_capture_to_geometry_ms"],
        ),
        "capture_to_preview_p95": within(
            "capture_to_preview_ms",
            acceptance["max_p95_capture_to_preview_ms"],
        ),
        "stereo_readout_skew_p95": stereo_check,
        "stale_rejections": (
            stale_rejections <= int(acceptance["maximum_stale_rejections"])
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "acceptance": acceptance,
        "checks": checks,
        "stale_rejections": stale_rejections,
        "metrics": metrics,
        "frames": frame_rows,
        "scope_note": (
            "Software timestamps end when the preview is queued. Measure true "
            "photon-to-display latency separately with an external high-speed camera."
        ),
    }


def write_report(report, destination: Path):
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description="Analyze GlareTracker latency logs")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("acceptance_json", type=Path)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("latency_report.json"),
    )
    args = parser.parse_args()
    report = analyze_latency(args.session_dir, args.acceptance_json)
    write_report(report, args.report)
    print(f"Latency validation: {report['status']}")
    print(args.report)
    raise SystemExit(0 if report["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
