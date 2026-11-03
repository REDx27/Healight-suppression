"""Find a readable OpenCV mode for one problematic camera index."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import cv2


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _open(index, backend):
    return cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)


def _set_profile(capture, width, height, fourcc, fps):
    if fourcc:
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    if width:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if fps:
        capture.set(cv2.CAP_PROP_FPS, fps)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=int)
    parser.add_argument("--frames", type=int, default=20)
    args = parser.parse_args()
    output = (PROJECT_ROOT / "diagnostics" / "camera_mode_probe" /
              datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(parents=True, exist_ok=True)
    backends = [("directshow", cv2.CAP_DSHOW),
                ("media_foundation", cv2.CAP_MSMF), ("automatic", None)]
    profiles = [
        ("driver_default", None, None, None, None),
        ("640x480_mjpg_30", 640, 480, "MJPG", 30),
        ("640x480_yuy2_30", 640, 480, "YUY2", 30),
        ("640x480_mjpg_15", 640, 480, "MJPG", 15),
        ("320x240_mjpg_30", 320, 240, "MJPG", 30),
        ("320x240_yuy2_15", 320, 240, "YUY2", 15),
        ("1280x720_mjpg_30", 1280, 720, "MJPG", 30),
    ]
    records = []
    for backend_name, backend in backends:
        for profile_name, width, height, fourcc, fps in profiles:
            capture = _open(args.index, backend)
            record = {"backend": backend_name, "profile": profile_name,
                      "opened": bool(capture.isOpened()), "successful_reads": 0}
            try:
                if not record["opened"]:
                    records.append(record)
                    print(f"{backend_name} {profile_name}: unavailable", flush=True)
                    continue
                _set_profile(capture, width, height, fourcc, fps)
                frame = None
                for _ in range(max(3, args.frames)):
                    ok, candidate = capture.read()
                    if ok and candidate is not None and candidate.size:
                        record["successful_reads"] += 1
                        frame = candidate
                    time.sleep(0.03)
                record["readback"] = {
                    "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fps": float(capture.get(cv2.CAP_PROP_FPS)),
                    "fourcc": int(capture.get(cv2.CAP_PROP_FOURCC)),
                }
                if frame is not None:
                    name = f"{backend_name}_{profile_name}.png"
                    cv2.imwrite(str(output / name), frame)
                    record["image"] = name
                print(
                    f"{backend_name} {profile_name}: reads={record['successful_reads']}; "
                    f"readback={record.get('readback')}", flush=True)
            except Exception as error:
                record["error"] = f"{type(error).__name__}: {error}"
                print(f"{backend_name} {profile_name}: {record['error']}", flush=True)
            finally:
                capture.release()
                records.append(record)
    report = output / "report.json"
    report.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
