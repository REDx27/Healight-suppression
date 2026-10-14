# Driver and Road-Camera Ground-Truth Measurement Protocol

This protocol is Stage 3 of the
[`Validation Plan`](../plans/VALIDATION_PLAN.md). It measures the current
prototype; it does not validate the system for road use.

## Safety and scope

- Use a stationary indoor rig or closed laboratory area.
- Do not operate the prototype in a moving vehicle or on a public road.
- Do not look directly into high-power lamps. Use a diffused, current-limited
  test lamp and appropriate eye protection.
- Do not move a camera mount during one calibrated test set.
- Record failures and dropouts; do not delete inconvenient runs.

## Required equipment

- Rigid mounts for the driver and road cameras.
- Tape measure with millimetre markings; a square and spirit level are preferred.
- Diffused test lamp with fixed brightness and geometry.
- Position markers referenced to the software coordinate system.
- A clock-independent condition label for every repeated run.

## Declare limits before collecting final data

Complete these values in the research record before inspecting final results:

| Metric | Driver limit | Road-light limit |
|---|---:|---:|
| Mean 3D error (cm) | TBD | TBD |
| 95th-percentile 3D error (cm) | TBD | TBD |
| Maximum 3D error (cm) | TBD | TBD |
| Stationary jitter, 95th percentile (cm) | TBD | TBD |
| Detection availability (%) | TBD | TBD |
| Maximum dropout duration (ms) | TBD | TBD |

## Coordinate convention

- `X`: negative left, positive right.
- `Y`: driver behind the windshield is negative; road light in front is positive.
- `Z`: zero at the windshield bottom and positive upward.
- Measure from a documented physical origin. Photograph the origin and axis markers.

Camera-reported coordinates are not yet camera-to-windshield extrinsically
calibrated. Stage 3 therefore measures and documents current error; it must not be
used to claim physically trustworthy windshield coordinates.

## Before every test set

1. Photograph both mounts, the origin, tape/rail, lamp, and target markers.
2. Record camera identity, index, resolution, focus, exposure, gain, brightness,
   threshold, lighting, and calibration-profile identifiers.
3. Start the application and select the required operating mode.
4. Enable **Record timestamped CSV and camera video**.
5. Confirm that the recording directory is displayed and both expected previews
   are live.
6. Run a short trial, stop recording, and verify `telemetry.csv`,
   `video_timestamps.csv`, `session.json`, and each expected `.avi` can be opened.
7. Before the final matrix, run the required ten-minute dual-camera recording and
   verify zero unexplained telemetry loss and decodable video.

## Operator marking workflow

For every stable measured position:

1. Select the ground-truth target in **Research Recording**.
2. Enter a unique condition ID.
3. Enter tape-measured `X`, `Y`, and `Z` in centimetres.
4. Hold the target stationary and wait at least two seconds for settling.
5. Click **Mark Measured Position**.
6. Hold the condition unchanged for ten seconds.
7. Move to the next condition and repeat.

Each marker is written directly into `telemetry.csv` with UTC time, monotonic time,
condition ID, target type, and measured coordinates. Use at least three independently
repositioned repeats per condition; do not obtain repeats by merely copying a row.

## Driver baseline matrix

Use one variable at a time around the normal seated reference. Suggested minimum:

| Family | Values | Repeats | Hold |
|---|---|---:|---:|
| Depth `Y` | -40, -50, -60, -75 cm | 3 | 10 s |
| Lateral `X` | -10, 0, +10 cm at nominal depth | 3 | 10 s |
| Height `Z` | nominal -5, nominal, nominal +5 cm | 3 | 10 s |
| Yaw | -20, -10, 0, +10, +20 degrees | 3 | 10 s |
| Pitch | -10, 0, +10 degrees | 3 | 10 s |
| Roll | -15, 0, +15 degrees | 3 | 10 s |
| Visibility | no glasses, normal glasses, blink sequence, one-eye occlusion | 3 | 10 s |
| Illumination | low, nominal, bright, rear backlight | 3 | 10 s |

For pose-only conditions, keep the measured eye midpoint fixed as closely as
possible. Use an independent physical reference for the eye midpoint; camera output
must not be used as ground truth.

Condition IDs should be stable and sortable, for example:

```text
DRV-D050-X000-Z010-YAW+00-R1
DRV-D050-X010-Z010-YAW+20-R2
```

## Road-light baseline matrix

Use the same diffused lamp, fixed exposure, focus, threshold, and camera mount for
the one-camera range demonstration:

| Family | Values | Repeats | Hold |
|---|---|---:|---:|
| Depth `Y` | +100, +150, +200, +300, +500 cm | 3 | 10 s |
| Lateral `X` | -50, -25, 0, +25, +50 cm | 3 | 10 s |
| Height `Z` | 5, 10, 15, 20 cm | 3 | 10 s |
| Angle | -20, -10, 0, +10, +20 degrees | 3 | 10 s |
| Intensity | low, nominal, high without saturation | 3 | 10 s |

Use maximum-sources `1` for this baseline so each marker maps unambiguously to the
controlled lamp. Additional lamp types and multi-source tests belong to the robustness
matrix after baseline performance is known.

Example condition ID:

```text
LAMP-D200-X+025-Z010-A+00-R1
```

The monocular apparent-size method is valid only for the lamp and settings used for
its calibration. Report results as controlled demonstration accuracy, not general
headlight ranging accuracy.

## Analysis

After stopping recording, run:

```powershell
py -3.13 scripts/analyze_ground_truth.py diagnostics\<session-directory>
```

The analyzer assigns tracking samples to the ten-second window following each
ground-truth marker and writes:

- `ground_truth_summary.csv` for per-condition results;
- `ground_truth_summary.json` for machine-readable metadata and metrics.

Review the synchronized video for every dropout, outlier, or unexpected result.
Never remove an outlier without retaining the raw row and documenting the exclusion
rule and reason.

## Completion evidence

Stage 3 remains open until the repository or research archive contains:

- the completed predeclared acceptance limits;
- setup photographs and camera/configuration metadata;
- the raw diagnostics directory for every run;
- at least three independently repositioned repeats per matrix condition;
- generated CSV/JSON summaries;
- a signed result note identifying passes, failures, exclusions, and limitations.
