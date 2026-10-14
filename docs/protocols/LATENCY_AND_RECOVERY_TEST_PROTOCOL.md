# Latency and Failure-Recovery Test Protocol

This is Stage 6 of the
[`Validation Plan`](../plans/VALIDATION_PLAN.md). Software timestamps support diagnosis,
but an external optical measurement is required for true photon-to-display latency.

## Instrumented stages

When research recording is active, the application records monotonic timestamps for:

- capture/read start and completion;
- detection completion;
- worker signal arrival on the GUI thread;
- geometry completion;
- preview queueing;
- stereo primary/secondary readout-completion skew;
- rejected stale samples.

Samples older than 250 ms at the GUI tracking callback are rejected and tracking
output is cleared. This is a prototype guard, not a validated automotive deadline.

## Predeclare limits

Create an acceptance JSON before final testing:

```json
{
  "minimum_complete_samples": 1000,
  "max_p95_capture_to_geometry_ms": 60,
  "max_p95_capture_to_preview_ms": 80,
  "max_p95_stereo_readout_skew_ms": 10,
  "maximum_stale_rejections": 0
}
```

These values are examples only. Select justified limits based on the motion and
blocker-size error budget.

Analyze a recorded session with:

```powershell
py -3.13 scripts/analyze_latency.py diagnostics\<session> latency_acceptance.json `
  --report latency_report.json
```

## Software timing matrix

Run each condition for at least two minutes and report mean, median, p95, and maximum:

1. driver camera only, stationary target;
2. road camera only, stationary lamp;
3. both single cameras active;
4. stereo road cameras plus driver camera;
5. maximum configured source count;
6. simultaneous video/CSV recording;
7. light movement simulation;
8. CPU load representative of the target computer.

Report encoded-video drops and telemetry-row drops from `session.json`. A timing run
with unexplained dropped telemetry is invalid.

## External photon-to-display latency

Software preview queueing is not physical display completion. Use a high-speed camera
that sees both:

- an LED whose state transition is the optical input; and
- the LCD/blocker/display response.

Record at a known frame rate high enough for the required uncertainty. Count frames
between optical transition and visible blocker response. Repeat at least 100 times,
including motion in both directions. Report camera-frame quantization uncertainty.

## Failure injection matrix

With a safe stationary rig, inject each failure independently:

| Failure | Required observation |
|---|---|
| Cover driver camera | Eye state invalid; all blockers cleared within limit |
| Cover road camera | Light state invalid; all blockers cleared within limit |
| Disconnect driver camera | Offline status, no stale eye use, clean reconnect/stop |
| Disconnect each road camera | Offline status, no stale light use |
| Freeze/replay old frame | Sample exceeds freshness limit and is rejected |
| Remove face/light | Lost state logged and blocker cleared |
| Invalid extrinsic profile | Profile rejected before output activation |
| Change resolution/device/mount ID | Old profile rejected |
| Fill/deny log destination | Tracking remains safe; recording error is visible |
| Stop during recording | CSV/video flush and application exits cleanly |
| Camera read stalls | UI remains responsive; stale output clears |

For every case, record injection time, invalid-state detection time, blocker-clear time,
recovery time, final state, logs, and synchronized video.

## Recovery policy

- Failure must default to no blocking output.
- Recovery must require a fresh valid eye and fresh valid light observation.
- Previously calculated intersections must not reappear after mode/camera changes.
- Reconnection must not silently reuse an incompatible calibration profile.
- Automatic recovery and operator-required recovery must be documented separately.

## Exit evidence

- software latency report for every operating mode;
- external photon-to-display distribution and uncertainty;
- complete failure-injection matrix with synchronized evidence;
- proof that stale/invalid states clear output inside the declared deadline;
- documented prediction comparison, if prediction is introduced.

Stage 6 remains incomplete until the physical timing and complete failure-injection
matrix pass their predeclared limits.
