# GlareTracker Ordered Validation Plan

> Started: 2026-10-14
> Rule: complete the stages in order. A written protocol is preparation, not a
> test pass. Hardware-dependent stages remain open until measurements and
> evidence files have been collected.

Current software verification: **112 automated tests passed on Python 3.13** on
2026-11-04. This does not satisfy any open physical exit criterion.

## Immediate prerequisite: road stereo bring-up (2026-10-27)

The operator confirmed two road cameras plus the driver camera. Single-camera
light detection worked with a sunglass lens; the second stereo feed opened but
the stereo result was not working reliably. Accuracy remains unmeasured and poor
by operator observation. This supersedes the earlier camera-availability blocker.

At the operator's request, complete this prerequisite before resuming the remaining
eight stages in order. Do not interpret a calibration fit as a stage 3 or 4 pass.

- [x] Add paired chessboard capture, intrinsic/stereo fitting, fit-quality gates,
      raw evidence retention and ordered-camera/resolution-bound profiles.
- [x] Remove assumed stereo depth fallback; add per-view candidate/match diagnostics.
- [x] Hide monocular range and manual simulation controls in stereo tuning mode.
- [x] Add camera-free synthetic/profile/UI/runtime regression tests.
- [ ] Rigidly fix the road cameras and final optical filters; measure the board.
- [ ] Capture at least 15 varied paired board poses and accept a physically plausible fit.
- [ ] Verify stationary-light depth at independently measured distances; tune each feed.
- [ ] Reintroduce live driver tracking, then resume recording soak and stages 3–8.

Procedure: [STEREO_CHESSBOARD_SETUP_GUIDE.md](../guides/STEREO_CHESSBOARD_SETUP_GUIDE.md).

The proposed replacement workflow—including startup consent, independent ChArUco
intrinsics, post-sunglass verification, sparse bright-point correspondence and UI
reduction—is specified in
[STEREO_CAMERA_BRINGUP_AND_UI_SIMPLIFICATION_PLAN.md](STEREO_CAMERA_BRINGUP_AND_UI_SIMPLIFICATION_PLAN.md).
That document is an implementation plan, not evidence that the physical items above
have passed.

## Status summary

| Stage | Validation workstream | Status | Completion evidence |
|---:|---|---|---|
| 1 | Geometry unit and boundary tests | **Complete** | 15 focused tests pass |
| 2 | Timestamped CSV/video logging | **Software complete; live soak pending** | Recorder, UI integration, tests, then ten-minute dual-camera run |
| 3 | Driver and road-camera ground-truth measurements | **Ready for physical collection** | Protocol, embedded markers, analyzer, then measured results |
| 4 | Camera-to-windshield calibration testing | **Software ready; physical validation pending** | Guarded pose fitting plus held-out measured target error |
| 5 | End-to-end physical intersection testing | **Analyzer ready; physical trials pending** | Independent error decomposition plus measured trials |
| 6 | Latency and failure-recovery testing | **Instrumentation ready; physical tests pending** | Software timing, stale rejection, external latency, and failure matrix |
| 7 | Physical LCD validation | **Experimental output ready; bench validation pending** | Fail-safe renderer plus optical/alignment evidence |
| 8 | Environmental and vehicle-like testing | **Protocol ready; execution pending** | Gated bench/environment/closed-course evidence |

## 1. Geometry unit and boundary tests

- [x] Test valid ray-to-windshield intersections.
- [x] Reject parallel and non-crossing ray segments.
- [x] Test fallback pixel-to-centimetre conversion.
- [x] Test intrinsic-calibrated pixel unprojection.
- [x] Test LCD centre, corners, exact boundaries, and out-of-bounds points.
- [x] Fix the bottom-right LCD mapping overflow.
- [x] Test IPD depth and yaw compensation.
- [x] Run the complete automated regression suite.

Exit evidence: `tests/test_geometry.py`; 15 focused tests pass and the current
complete suite contains 112 passing tests on Python 3.13.

## 2. Timestamped CSV/video logging

- [x] Create one uniquely named directory for each recording session.
- [x] Record UTC wall-clock time and monotonic time for every telemetry event.
- [x] Record eye coordinates, light coordinates/confidence/state, calculated
      intersections, camera health, and session-state changes.
- [x] Record driver, primary-road, and secondary-road video streams when present.
- [x] Create a sidecar CSV mapping every encoded video frame to its capture time.
- [x] Store session metadata and software/configuration values.
- [x] Keep video encoding off the GUI thread and report dropped frames/errors.
- [x] Add an explicit operator control and visible recording path/status.
- [x] Stop and flush recording safely during application shutdown.
- [x] Add automated CSV, metadata, video, and shutdown tests.
- [x] Add a strict finalized-session verifier for duration, timestamp order, exact
      streams, sidecar/manifest/decode counts, frame continuity, drops and errors.
- [ ] Complete and inspect a ten-minute dual-camera physical recording.

Exit criteria: a ten-minute dual-camera recording closes cleanly; CSV timestamps
are ordered; all video streams can be decoded; frame sidecars identify every
encoded frame; no unexplained telemetry loss occurs.

## 3. Driver and road-camera ground-truth measurements

- [ ] Freeze camera mounts, resolution, focus, exposure, and lighting settings.
- [x] Define measured driver positions covering centre, lateral/vertical offsets,
      multiple depths, yaw, pitch, roll, glasses, blinks, and partial occlusion.
- [x] Define road-light positions covering multiple lateral/vertical offsets and
      depths, multiple lamps, intensities, and approach angles.
- [x] Add timestamped in-application ground-truth position markers.
- [x] Add per-condition bias, error, RMSE, percentile, and jitter analysis.
- [ ] Record at least three repeated runs at each position.
- [ ] Export raw samples, ground truth, mean error, RMSE, 95th-percentile error,
      jitter, detection rate, and dropout duration.
- [ ] Save synchronized videos, CSV files, setup photographs, and configuration.
- [ ] Enter acceptance limits in the protocol before inspecting final results.

Exit criteria: the complete measurement matrix is repeatable and includes enough
evidence for another operator to reproduce every reported number.

## 4. Camera-to-windshield calibration testing

- [x] Define and store a rigid camera-to-windshield rotation and translation.
- [x] Unit-test identity, translation, rotation, inverse, and composition cases.
- [x] Reject malformed/non-rigid transforms and incompatible camera profiles.
- [x] Add solvePnP fitting, held-out physical target validation, and guarded profile
      output using predeclared limits.
- [ ] Measure known targets across the windshield centre, edges, and corners.
- [ ] Calculate per-target error, RMSE, maximum error, and repeatability.
- [ ] Repeat after camera remounting and verify stale calibration is rejected.

Exit criteria: all tracked eye/light data is expressed in one windshield frame
and meets a predeclared centimetre-error limit across the usable area.

## 5. End-to-end physical intersection testing

- [ ] Place eye and lamp targets at independently measured 3D coordinates.
- [ ] Calculate the reference ray-plane intersection outside the application.
- [ ] Compare application output with a marked windshield target.
- [ ] Cover both eyes, multiple lights, head roll, near/far distances, and all
      windshield regions.
- [ ] Separate calibration error, tracking error, and geometry error.
- [ ] Report mean, RMSE, maximum, and 95th-percentile physical error.
- [x] Add an independent reference calculation and guarded analyzer that separates
      input, physical-marking, propagation, geometry, and end-to-end errors.

Exit criteria: predicted intersections agree with physical targets within the
predeclared tolerance for the full test matrix.

## 6. Latency and failure-recovery testing

- [x] Timestamp capture, detection, GUI delivery, geometry, and preview queueing.
- [x] Add stale-sample rejection and timing-distribution analysis.
- [ ] Measure driver/road camera skew and end-to-end latency distributions.
- [ ] Test stationary and moving eye/light cases at expected maximum speeds.
- [ ] Disconnect, stall, cover, and reconnect each camera independently.
- [ ] Test lost face, lost light, stale samples, invalid calibration, write errors,
      and application shutdown during recording.
- [ ] Verify blocking output clears within the declared fail-safe deadline.
- [ ] Evaluate whether prediction reduces moving-target error without overshoot.

Exit criteria: latency and recovery limits are declared and satisfied, with no
stale blocker remaining active after an invalid tracking state.

## 7. Physical LCD validation

- [ ] Characterize the stripped panel's transparent state, dark-state attenuation,
      viewing angle, polarization, ghosting, refresh rate, and thermal behaviour.
- [ ] Calibrate LCD pixels to physical windshield coordinates.
- [ ] Test centre, edge, corner, and sub-region alignment targets.
- [ ] Determine blocker diameter from pupil uncertainty, optical spread, and latency.
- [ ] Validate simultaneous coverage of both pupils and multiple light sources.
- [ ] Verify the panel returns immediately to its safe transparent state on failure.
- [x] Add disabled-by-default secondary-display output, feathered spots, exact pixel
      bounds, and white fail-safe clearing on lost/stale/stop/shutdown states.

Exit criteria: rendered blocker spots physically cover the measured light-to-eye
rays throughout the declared viewing region without unacceptable visibility loss.

## 8. Environmental and vehicle-like testing

- [ ] Test daylight, dusk, night, backlight, streetlights, and reflections.
- [ ] Test dry, wet, fog-like, and glare-producing optical conditions safely in a
      stationary rig before any closed-course work.
- [ ] Test vibration spectra and mount movement representative of a vehicle.
- [ ] Test declared cold, ambient, and hot operating temperatures.
- [ ] Test glasses, sunglasses, multiple drivers, skin tones, and seating positions.
- [ ] Test motorcycles, cars, multiple lights, occlusions, crossings, and LED flicker.
- [ ] Run endurance tests and inspect CPU, memory, temperature, dropped frames, and
      calibration drift.
- [ ] Perform a formal hazard review before any vehicle trial; do not test on public
      roads or treat the prototype as a safety device.
- [x] Define phased illumination, weather-like, thermal, vibration, endurance,
      stationary-rig, combined-worst-case, and conditional closed-course protocols.

Exit criteria: evidence supports every declared operating limit, known failures are
documented, and any vehicle-like test has an approved stationary/closed-course safety
procedure.

## Evidence index

Add links here as work is completed:

- Stage 1: `tests/test_geometry.py`
- Stage 2: `glare_tracker/diagnostics.py`,
  `scripts/verify_recording_session.py`, `tests/test_diagnostics.py`,
  `tests/test_recording_verification.py`,
  `docs/protocols/TIMESTAMPED_RECORDING_SOAK_PROTOCOL.md`
- Stage 3: `docs/protocols/GROUND_TRUTH_MEASUREMENT_PROTOCOL.md`,
  `scripts/analyze_ground_truth.py`, `tests/test_ground_truth_analysis.py`
- Stage 4: `glare_tracker/extrinsics.py`, `scripts/calibrate_extrinsics.py`,
  `docs/protocols/CAMERA_TO_WINDSHIELD_CALIBRATION_PROTOCOL.md`,
  `tests/test_extrinsics.py`, `tests/test_extrinsic_calibration_workflow.py`
- Stage 5: `scripts/analyze_physical_intersections.py`,
  `docs/protocols/PHYSICAL_INTERSECTION_TEST_PROTOCOL.md`,
  `tests/test_physical_intersection_analysis.py`
- Stage 6: `scripts/analyze_latency.py`,
  `docs/protocols/LATENCY_AND_RECOVERY_TEST_PROTOCOL.md`,
  `tests/test_latency_recovery.py`
- Stage 7: `glare_tracker/lcd_blocker.py`,
  `docs/protocols/PHYSICAL_LCD_VALIDATION_PROTOCOL.md`, `tests/test_lcd_blocker.py`
- Stage 8: `docs/protocols/ENVIRONMENTAL_AND_VEHICLE_TEST_PROTOCOL.md`
