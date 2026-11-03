"""Probe every OpenCV camera backend and save objective detection evidence.

Usage:
    py -3.13 scripts/probe_cameras.py --max-index 6

Close GlareTracker and other camera applications before running this command.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from glare_tracker.capture import configure_video_capture  # noqa: E402
from glare_tracker.headlight_detector import (  # noqa: E402
    LightDetectionSettings,
    process_bright_spots,
)


def _backends():
    values = [("automatic", None)]
    if sys.platform.startswith("win"):
        values = [
            ("directshow", cv2.CAP_DSHOW),
            ("media_foundation", cv2.CAP_MSMF),
            ("automatic", None),
        ]
    return values


def _open(index, backend):
    return cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)


def _frame_metrics(frame, detection):
    gray = detection.gray
    observations = [
        {
            "center": [round(value, 2) for value in item.center],
            "diameter_px": round(item.diameter_px, 2),
            "area_px": round(item.area_px, 2),
            "confidence": round(item.confidence, 3),
            "method": item.detection_method,
        }
        for item in detection.observations
    ]
    return {
        "shape": list(frame.shape),
        "mean_intensity": round(float(np.mean(gray)), 2),
        "p50_intensity": round(float(np.percentile(gray, 50)), 2),
        "p95_intensity": round(float(np.percentile(gray, 95)), 2),
        "p99_intensity": round(float(np.percentile(gray, 99)), 2),
        "peak_intensity": int(np.max(gray)),
        "clipped_fraction": round(float(np.mean(gray >= 250)), 6),
        "dark_fraction": round(float(np.mean(gray <= 5)), 6),
        "laplacian_variance": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
        "detector_threshold": round(float(detection.threshold_used), 2),
        "saliency_threshold": round(float(detection.saliency_threshold), 2),
        "detected_sources": len(observations),
        "observations": observations,
    }


def probe(index, backend_name, backend, output_dir, frame_count):
    record = {"index": index, "backend": backend_name, "opened": False}
    capture = _open(index, backend)
    try:
        record["opened"] = bool(capture.isOpened())
        if not record["opened"]:
            return record
        width, height, fps = configure_video_capture(capture)
        record["requested_profile_readback"] = {
            "width": width, "height": height, "fps": round(fps, 3),
        }
        successful = 0
        frame = None
        started = time.perf_counter()
        for _ in range(frame_count):
            ok, candidate = capture.read()
            if ok and candidate is not None and candidate.size:
                successful += 1
                frame = candidate
            time.sleep(0.02)
        elapsed = time.perf_counter() - started
        record["successful_reads"] = successful
        record["attempted_reads"] = frame_count
        record["observed_read_fps"] = round(successful / max(elapsed, 1e-6), 2)
        if frame is None:
            record["error"] = "Backend opened but returned no usable frames"
            return record
        detection = process_bright_spots(frame, LightDetectionSettings())
        record.update(_frame_metrics(frame, detection))
        stem = f"camera_{index}_{backend_name}"
        image_path = output_dir / f"{stem}.png"
        mask_path = output_dir / f"{stem}_mask.png"
        if cv2.imwrite(str(image_path), frame):
            record["image"] = image_path.name
        if cv2.imwrite(str(mask_path), detection.mask):
            record["mask"] = mask_path.name
        return record
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {error}"
        return record
    finally:
        capture.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-index", type=int, default=6)
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output_dir = args.output or (
        PROJECT_ROOT / "diagnostics" / "camera_probe_" /
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index in range(max(1, args.max_index)):
        for backend_name, backend in _backends():
            result = probe(index, backend_name, backend, output_dir, max(3, args.frames))
            records.append(result)
            state = "OK" if result.get("successful_reads") else (
                "OPEN-NO-FRAMES" if result.get("opened") else "unavailable")
            print(
                f"camera {index} {backend_name}: {state}; "
                f"reads={result.get('successful_reads', 0)}; "
                f"sources={result.get('detected_sources', 0)}; "
                f"error={result.get('error', '-')}",
                flush=True,
            )
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "opencv_version": cv2.__version__,
        "settings": LightDetectionSettings().__dict__,
        "records": records,
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
