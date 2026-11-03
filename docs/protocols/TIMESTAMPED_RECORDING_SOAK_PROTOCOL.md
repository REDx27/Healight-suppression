# Timestamped CSV/Video Recording Soak Protocol

This is the physical completion procedure for Stage 2 of the
[Validation Plan](../plans/VALIDATION_PLAN.md). The recorder and verifier can be
software-tested without cameras, but Stage 2 passes only after a real, finalized
ten-minute session meets limits declared before the run.

## Scope and safety

Use a stationary laboratory rig. This test validates recording continuity and file
integrity; it does not validate camera synchronization, coordinate accuracy, road use,
or glare suppression. Keep the LCD blocker output disabled.

The current prerequisite is the rigid two-road-camera chessboard setup in the
[Road Stereo Chessboard Setup Guide](../guides/STEREO_CHESSBOARD_SETUP_GUIDE.md).
Do not move the road pair between stereo calibration and the soak.

## Predeclare the run

Create `recording_acceptance.json` before starting. For the first road-stereo soak,
use this structure and replace example thresholds only with justified values:

```json
{
  "minimum_duration_s": 600,
  "expected_streams": ["road_primary", "road_secondary"],
  "minimum_telemetry_rows": 1000,
  "minimum_frames_per_stream": 3000,
  "minimum_average_fps": {
    "road_primary": 5.0,
    "road_secondary": 5.0
  },
  "maximum_frame_gap_ms": 1000,
  "maximum_stream_start_delay_ms": 5000,
  "maximum_stream_end_delay_ms": 5000,
  "maximum_dropped_video_frames": 0,
  "maximum_dropped_telemetry_rows": 0,
  "maximum_recording_errors": 0
}
```

For the later Fully Auto three-camera run, add `driver` to `expected_streams` and
`"driver": 7.0` to `minimum_average_fps`. The stream list must exactly match the
operating mode. A lower limit chosen after seeing a failure is not valid evidence;
declare and justify a new run instead.

## Setup record

Before each attempt, record in the lab notes:

- date, operator, source commit, computer and power configuration;
- operating mode and camera indices/physical labels;
- requested and observed resolution/FPS, filters, focus and exposure state;
- stereo profile filename and measured baseline, when applicable;
- diagnostics output directory and acceptance-file checksum or archived copy;
- setup photographs showing all mounts and physical camera labels.

Camera indices are not stable hardware identities. Confirm each preview after every
reconnection. Both road-camera views must remain visible throughout the run.

## Execution

1. Close software that might own a camera. Launch `py -3.13 run.py`.
2. Refresh cameras while stopped. For the first soak, select **Driver Position
   Fixed**, **Stereo Cameras**, and the calibrated left/right road indices.
3. Select **Standby** and confirm both original previews are live. Correct any
   calibration-required or camera-read status before continuing.
4. Enable **Record timestamped CSV and camera video**. Copy the displayed session
   path into the lab notes.
5. Select **Run**. Keep at least one stationary test lamp visible in both road feeds.
   Include a few deliberate, labelled lamp movements, but do not disturb the rig.
6. Run for at least 10 minutes measured by the recorder; do not count setup time.
   Watch for offline, frame-read, writer, dropped-frame, or calibration warnings.
7. Select **Stop**, then disable recording. Wait until the UI reports the saved path.
   Close the app normally. Do not manually edit the session evidence.

If a camera or writer fails, preserve the attempt as a failed run. Repair the cause
and start a new session; never concatenate recordings to reach ten minutes.

## Machine verification

Run the verifier against the finalized directory:

```powershell
py -3.13 scripts/verify_recording_session.py diagnostics\<session> `
  recording_acceptance.json `
  --report diagnostics\<session>\recording_verification_report.json
```

The verifier performs a full decode of every expected AVI and checks:

- `session.json`, `telemetry.csv`, and `video_timestamps.csv` exist;
- the session has `stopped_utc` and meets the declared duration;
- telemetry and video timestamps never decrease and sequences increase;
- `recording_started` and `recording_stopped` events are present;
- the exact expected stream set was recorded;
- every stream starts/ends close enough to the session boundaries;
- sidecar indices are contiguous and counts agree with the manifest;
- every AVI frame decodes and equals the sidecar/manifest count;
- average FPS and maximum inter-frame gap meet declared limits; and
- drops and recorder errors remain within their declared limits.

Exit code `0` means the declared file-integrity checks passed; exit code `2` means
FAIL. A report PASS is necessary but not sufficient for later accuracy or latency
stages. Preview recordings are sequential observations and do not prove exposure or
hardware synchronization.

## Manual evidence review

Even after a machine PASS:

1. open each AVI at the beginning, middle and end;
2. confirm physical camera identity and view did not swap;
3. confirm lamp movements appear in both road videos in the expected order;
4. inspect `telemetry.csv` around the movements and any status changes;
5. archive the unmodified session, report, acceptance JSON, lab notes and photos;
6. record the software commit and a SHA-256 hash of the archived evidence.

Stage 2 is complete only when both machine and manual checks pass. Later Fully Auto
testing should repeat the soak with all three streams; it does not invalidate the
first ordered road-stereo gate.
