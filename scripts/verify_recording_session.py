"""Strictly verify a closed GlareTracker CSV/video recording session.

This tool supports the Stage 2 soak-test gate.  Acceptance limits must be
declared in JSON before a run; a report is produced without modifying evidence.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path

import cv2


REQUIRED_ACCEPTANCE = (
    "minimum_duration_s",
    "expected_streams",
    "minimum_telemetry_rows",
    "minimum_frames_per_stream",
    "minimum_average_fps",
    "maximum_frame_gap_ms",
    "maximum_stream_start_delay_ms",
    "maximum_stream_end_delay_ms",
    "maximum_dropped_video_frames",
    "maximum_dropped_telemetry_rows",
    "maximum_recording_errors",
)


def _read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def _integer(row, field, source):
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{source} contains an invalid {field}") from error


def _ordered(rows, field, source, *, strictly=True):
    values = [_integer(row, field, source) for row in rows]
    pairs = zip(values, values[1:])
    return all(right > left if strictly else right >= left for left, right in pairs)


def _parse_utc(value, field):
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"session.json contains an invalid {field}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"session.json {field} must include a UTC offset")
    return parsed


def _decode_video(path: Path):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        return 0, False
    count = 0
    valid = True
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame is None or frame.size == 0:
                valid = False
                break
            count += 1
    finally:
        capture.release()
    return count, valid


def _normalize_acceptance(data):
    missing = [field for field in REQUIRED_ACCEPTANCE if field not in data]
    if missing:
        raise ValueError(
            "Recording acceptance limits must be declared before analysis: "
            + ", ".join(missing)
        )
    streams = [str(value).strip() for value in data["expected_streams"]]
    if not streams or any(not value for value in streams) or len(set(streams)) != len(streams):
        raise ValueError("expected_streams must contain unique non-empty names")
    minimum_fps = data["minimum_average_fps"]
    if not isinstance(minimum_fps, dict) or set(minimum_fps) != set(streams):
        raise ValueError("minimum_average_fps must contain every expected stream exactly")
    normalized = dict(data)
    normalized["expected_streams"] = streams
    nonnegative = (
        "minimum_duration_s", "minimum_telemetry_rows",
        "minimum_frames_per_stream", "maximum_frame_gap_ms",
        "maximum_stream_start_delay_ms", "maximum_stream_end_delay_ms",
        "maximum_dropped_video_frames", "maximum_dropped_telemetry_rows",
        "maximum_recording_errors",
    )
    for field in nonnegative:
        if float(normalized[field]) < 0:
            raise ValueError(f"{field} cannot be negative")
    if any(float(value) < 0 for value in minimum_fps.values()):
        raise ValueError("minimum_average_fps values cannot be negative")
    return normalized


def verify_recording_session(session_dir: Path, acceptance_path: Path):
    """Return a detailed PASS/FAIL report for one finalized session."""
    session_dir = Path(session_dir)
    acceptance = _normalize_acceptance(
        json.loads(Path(acceptance_path).read_text(encoding="utf-8"))
    )
    expected = acceptance["expected_streams"]
    checks = {}
    issues = []

    def check(name, condition, issue):
        passed = bool(condition)
        checks[name] = passed
        if not passed:
            issues.append(issue)
        return passed

    required_files = ("session.json", "telemetry.csv", "video_timestamps.csv")
    missing_files = [name for name in required_files if not (session_dir / name).is_file()]
    check("required_files", not missing_files,
          "Missing required file(s): " + ", ".join(missing_files))
    if missing_files:
        return {"status": "FAIL", "session_dir": str(session_dir),
                "acceptance": acceptance, "checks": checks, "issues": issues,
                "streams": {}}

    manifest = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    started = _parse_utc(manifest.get("started_utc"), "started_utc")
    stopped_value = manifest.get("stopped_utc")
    check("session_finalized", stopped_value is not None,
          "session.json has no stopped_utc; the recording is not finalized")
    if stopped_value is None:
        stopped = started
    else:
        stopped = _parse_utc(stopped_value, "stopped_utc")
    duration_s = max(0.0, (stopped - started).total_seconds())
    check("minimum_duration", duration_s >= float(acceptance["minimum_duration_s"]),
          f"Duration {duration_s:.3f}s is below the declared minimum")
    errors = list(manifest.get("errors", []))
    dropped_video = int(manifest.get("dropped_video_frames", -1))
    dropped_telemetry = int(manifest.get("dropped_telemetry_rows", -1))
    check("recording_errors", len(errors) <= int(acceptance["maximum_recording_errors"]),
          f"session.json records {len(errors)} recording error(s)")
    check("dropped_video_frames",
          0 <= dropped_video <= int(acceptance["maximum_dropped_video_frames"]),
          f"session.json records {dropped_video} dropped video frame(s)")
    check("dropped_telemetry_rows",
          0 <= dropped_telemetry <= int(acceptance["maximum_dropped_telemetry_rows"]),
          f"session.json records {dropped_telemetry} dropped telemetry row(s)")

    telemetry_fields, telemetry = _read_csv(session_dir / "telemetry.csv")
    needed_telemetry = {"sequence", "unix_time_ns", "monotonic_ns", "event"}
    check("telemetry_schema", needed_telemetry.issubset(telemetry_fields),
          "telemetry.csv is missing required timestamp/event fields")
    check("minimum_telemetry_rows",
          len(telemetry) >= int(acceptance["minimum_telemetry_rows"]),
          f"telemetry.csv contains only {len(telemetry)} data row(s)")
    if needed_telemetry.issubset(telemetry_fields) and telemetry:
        check("telemetry_sequence_order", _ordered(telemetry, "sequence", "telemetry.csv"),
              "telemetry.csv sequence is not strictly increasing")
        check("telemetry_monotonic_order",
              _ordered(telemetry, "monotonic_ns", "telemetry.csv", strictly=False),
              "telemetry.csv monotonic_ns decreases")
        check("telemetry_unix_order",
              _ordered(telemetry, "unix_time_ns", "telemetry.csv", strictly=False),
              "telemetry.csv unix_time_ns decreases")
        events = [row.get("event") for row in telemetry]
        check("recording_boundary_events",
              "recording_started" in events and "recording_stopped" in events,
              "telemetry.csv lacks recording_started or recording_stopped")

    video_fields, video_rows = _read_csv(session_dir / "video_timestamps.csv")
    needed_video = {"sequence", "unix_time_ns", "monotonic_ns", "stream",
                    "frame_index", "width", "height", "video_file"}
    check("video_timestamp_schema", needed_video.issubset(video_fields),
          "video_timestamps.csv is missing required fields")
    if needed_video.issubset(video_fields) and video_rows:
        check("video_sequence_order", _ordered(video_rows, "sequence", "video_timestamps.csv"),
              "video_timestamps.csv sequence is not strictly increasing")
        check("video_monotonic_order",
              _ordered(video_rows, "monotonic_ns", "video_timestamps.csv", strictly=False),
              "video_timestamps.csv monotonic_ns decreases")
        check("video_unix_order",
              _ordered(video_rows, "unix_time_ns", "video_timestamps.csv", strictly=False),
              "video_timestamps.csv unix_time_ns decreases")

    rows_by_stream = {stream: [] for stream in expected}
    unexpected = set()
    for row in video_rows:
        stream = row.get("stream", "")
        if stream in rows_by_stream:
            rows_by_stream[stream].append(row)
        else:
            unexpected.add(stream)
    manifest_counts = manifest.get("video_frames", {})
    actual_manifest_streams = set(manifest_counts)
    check("expected_stream_set", actual_manifest_streams == set(expected),
          "session stream set differs from expected: "
          f"actual={sorted(actual_manifest_streams)}, expected={sorted(expected)}")
    check("no_unexpected_sidecar_streams", not unexpected,
          f"video_timestamps.csv contains unexpected stream(s): {sorted(unexpected)}")

    started_ns = int(started.timestamp() * 1_000_000_000)
    stopped_ns = int(stopped.timestamp() * 1_000_000_000)
    stream_reports = {}
    for stream in expected:
        rows = rows_by_stream[stream]
        prefix = f"stream_{stream}"
        sidecar_count = len(rows)
        manifest_count = int(manifest_counts.get(stream, -1))
        check(f"{prefix}_minimum_frames",
              sidecar_count >= int(acceptance["minimum_frames_per_stream"]),
              f"{stream} has only {sidecar_count} sidecar frame(s)")
        indices = [_integer(row, "frame_index", "video_timestamps.csv") for row in rows]
        check(f"{prefix}_contiguous_indices", indices == list(range(sidecar_count)),
              f"{stream} frame indices are not contiguous from zero")
        check(f"{prefix}_manifest_count", manifest_count == sidecar_count,
              f"{stream} manifest count {manifest_count} != sidecar count {sidecar_count}")
        files = {row.get("video_file", "") for row in rows}
        expected_file = f"{stream}.avi"
        check(f"{prefix}_single_file", files == {expected_file},
              f"{stream} sidecar does not consistently name {expected_file}")
        dimensions_valid = all(
            _integer(row, "width", "video_timestamps.csv") > 0
            and _integer(row, "height", "video_timestamps.csv") > 0 for row in rows)
        check(f"{prefix}_dimensions", dimensions_valid,
              f"{stream} has an invalid frame dimension")

        timestamps = [_integer(row, "unix_time_ns", "video_timestamps.csv") for row in rows]
        average_fps = 0.0
        max_gap_ms = None
        start_delay_ms = end_delay_ms = None
        if timestamps:
            start_delay_ms = max(0.0, (timestamps[0] - started_ns) / 1_000_000.0)
            end_delay_ms = max(0.0, (stopped_ns - timestamps[-1]) / 1_000_000.0)
            gaps = [(b - a) / 1_000_000.0 for a, b in zip(timestamps, timestamps[1:])]
            max_gap_ms = max(gaps, default=0.0)
            span_s = max(0.0, (timestamps[-1] - timestamps[0]) / 1_000_000_000.0)
            average_fps = ((sidecar_count - 1) / span_s
                           if sidecar_count > 1 and span_s > 0 else 0.0)
        check(f"{prefix}_start_delay", start_delay_ms is not None and
              start_delay_ms <= float(acceptance["maximum_stream_start_delay_ms"]),
              f"{stream} starts too late or has no timestamp rows")
        check(f"{prefix}_end_delay", end_delay_ms is not None and
              end_delay_ms <= float(acceptance["maximum_stream_end_delay_ms"]),
              f"{stream} ends too early or has no timestamp rows")
        check(f"{prefix}_maximum_gap", max_gap_ms is not None and
              max_gap_ms <= float(acceptance["maximum_frame_gap_ms"]),
              f"{stream} has an excessive inter-frame gap")
        check(f"{prefix}_average_fps",
              average_fps >= float(acceptance["minimum_average_fps"][stream]),
              f"{stream} average FPS {average_fps:.3f} is below its limit")

        video_path = session_dir / expected_file
        video_exists = video_path.is_file()
        check(f"{prefix}_video_exists", video_exists,
              f"Missing video file {expected_file}")
        decoded_count, decoded_valid = _decode_video(video_path) if video_exists else (0, False)
        check(f"{prefix}_video_decodes", decoded_valid and decoded_count == sidecar_count,
              f"{stream} decoded {decoded_count} frame(s), expected {sidecar_count}")
        stream_reports[stream] = {
            "manifest_frames": manifest_count,
            "sidecar_frames": sidecar_count,
            "decoded_frames": decoded_count,
            "average_fps": average_fps,
            "maximum_frame_gap_ms": max_gap_ms,
            "start_delay_ms": start_delay_ms,
            "end_delay_ms": end_delay_ms,
        }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "session_dir": str(session_dir),
        "acceptance": acceptance,
        "duration_s": duration_s,
        "telemetry_rows": len(telemetry),
        "dropped_video_frames": dropped_video,
        "dropped_telemetry_rows": dropped_telemetry,
        "recording_errors": errors,
        "checks": checks,
        "issues": issues,
        "streams": stream_reports,
        "scope_note": (
            "This proves file/timestamp continuity and decodability for the recorded "
            "preview streams. It does not prove physical synchronization or accuracy."
        ),
    }


def write_report(report, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Verify a finalized GlareTracker research recording")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("acceptance_json", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    destination = args.report or args.session_dir / "recording_verification_report.json"
    try:
        report = verify_recording_session(args.session_dir, args.acceptance_json)
    except Exception as error:
        report = {"status": "FAIL", "session_dir": str(args.session_dir),
                  "checks": {}, "issues": [str(error)], "streams": {}}
    write_report(report, destination)
    print(f"Recording verification: {report['status']}")
    print(destination)
    raise SystemExit(0 if report["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
