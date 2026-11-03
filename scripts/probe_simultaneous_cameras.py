"""Open several cameras together and report per-stream delivery reliability."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import cv2


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from glare_tracker.capture import configure_video_capture, open_video_capture  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("indices", nargs="+", type=int)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--high-res-index", type=int,
        help="Keep this camera at 640x480/30 while other indices use the requested mode.")
    args = parser.parse_args()
    output = (PROJECT_ROOT / "diagnostics" / "simultaneous_camera_probe" /
              datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    output.mkdir(parents=True, exist_ok=True)
    streams = []
    try:
        for index in args.indices:
            capture, backend = open_video_capture(index)
            record = {"index": index, "backend": backend, "opened": capture is not None,
                      "grab_attempts": 0, "grab_successes": 0, "frames": 0}
            if capture is None:
                streams.append((None, record, None))
                print(f"camera {index}: unavailable", flush=True)
                continue
            if index == args.high_res_index:
                mode = configure_video_capture(capture, width=640, height=480, fps=30)
            else:
                mode = configure_video_capture(
                    capture, width=args.width, height=args.height, fps=args.fps)
            record["mode"] = [mode[0], mode[1], mode[2]]
            streams.append((capture, record, None))
            print(f"camera {index}: {backend}, mode={mode}", flush=True)

        deadline = time.perf_counter() + max(1.0, args.seconds)
        while time.perf_counter() < deadline:
            for capture, record, _ in streams:
                if capture is not None:
                    record["grab_attempts"] += 1
                    if capture.grab():
                        record["grab_successes"] += 1
            updated = []
            for capture, record, last_frame in streams:
                if capture is not None:
                    ok, frame = capture.retrieve()
                    if ok and frame is not None and frame.size:
                        record["frames"] += 1
                        last_frame = frame
                updated.append((capture, record, last_frame))
            streams = updated

        records = []
        for capture, record, frame in streams:
            if frame is not None:
                name = f"camera_{record['index']}.png"
                cv2.imwrite(str(output / name), frame)
                record["image"] = name
                record["frame_shape"] = list(frame.shape)
            records.append(record)
            print(json.dumps(record), flush=True)
        report = output / "report.json"
        report.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"Report: {report}")
    finally:
        for capture, _, _ in streams:
            if capture is not None:
                capture.release()


if __name__ == "__main__":
    main()
