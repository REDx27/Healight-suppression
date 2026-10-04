# GlareTracker Temporary System Workflow and Test Guide

> Date: 2026-10-02  
> Purpose: temporary reference for testing the current prototype and planning the
> final physical glare-suppression system.  
> Status: the current software is a research demonstration. It is not yet suitable
> for use in a moving vehicle.

## 1. What the final system is intended to do

The final GlareTracker system should:

1. Observe the driver's left and right eyes.
2. Measure or estimate the 3D position of each eye relative to the windshield.
3. Observe one or more bright road lights.
4. Measure the 3D position of each light relative to the windshield.
5. Draw a ray from each light to each eye.
6. Calculate where every ray crosses the windshield plane.
7. Convert each intersection from centimetres to LCD pixels.
8. Render a small dark blocking spot at each required LCD location.
9. Update the spots fast enough to follow head, vehicle, and light movement.
10. Remove blocking immediately if tracking becomes invalid.

The current prototype implements steps 1, 3, 5, 6, and the visualization parts of
steps 2 and 4. It contains the mathematical helper for step 7. The physical LCD output,
measurement-grade coordinate calibration, and full safety behaviour are not complete.

## 2. Current demonstration configuration

Use two independent cameras:

| Device | Index | Direction | Current job |
|---|---:|---|---|
| Integrated camera | 0 | Toward driver | Face, iris, and approximate driver-depth tracking |
| USB camera | 1 | Toward road/test lamp | Bright-light bearing and demonstration range estimation |

Do not assign one camera index to both jobs simultaneously. Most ordinary webcams
cannot be opened by both capture workers at the same time.

Current data flow:

```text
Driver camera 0
    -> MediaPipe face/iris landmarks
    -> eye pixel separation
    -> fixed fallback distance OR calibrated IPD depth estimate
    -> eye position (X, Y, Z)

Road camera 1
    -> adaptive bright-region detector
    -> filtered light centre + apparent bright-core diameter
    -> operator-supplied distance OR calibrated apparent-size estimate
    -> light position (X, Y, Z)

Eye position + light position
    -> eye-to-light ray
    -> intersection with windshield plane Y = 0
    -> 3D marker + 2D windshield marker + telemetry
```

### 2.1 Camera-development progress at this milestone

The project has moved beyond a UI-only camera demonstration. It now has a working
two-camera acquisition and estimation pipeline, but it has not yet reached
measurement-grade camera tracking.

| Camera workstream | Current state | Evidence and remaining boundary |
|---|---|---|
| Independent camera capture | **Implemented and live-tested** | Driver and road cameras run in separate workers; camera-index conflicts are rejected. DirectShow, Media Foundation, and automatic backend fallback are available. |
| USB camera compatibility | **Implemented and partly validated** | Both cameras request 640x480 MJPEG, 30 FPS, and a one-frame capture buffer. The tested USB road camera improved from 7 to 81 frames in 12 seconds. Other camera models still need regression testing. |
| Driver face and iris detection | **Implemented and live-tested** | A recorded run produced 94 driver frames and 93 eye detections in 10 seconds. Blink recovery, glasses, difficult lighting, and head-angle limits still need quantified tests. |
| Separate eye observations | **Implemented at the tracker output** | Left- and right-eye positions are emitted separately, but the active intersection calculation still uses their midpoint. Separate rays and blockers are not complete. |
| Driver distance estimation | **Demonstration feature implemented** | The guided wizard captures IPD and lens-to-eye distance, rejects unstable samples, saves a camera-specific profile, and enables live estimated depth. Accuracy at several distances and yaw angles remains unverified. |
| Road bright-light detection | **Implemented; final live regression pending** | Adaptive thresholding, weighted centroiding, temporal smoothing, candidate persistence, dropout hold, overexposure warning, and FPS telemetry exist. Synthetic blank rejection, centroid, smoothing, and dropout tests pass; the revised detector still requires physical lamp testing. |
| Single-camera road range | **Controlled demonstration only** | The guided wizard estimates distance from the apparent diameter of one calibrated lamp and labels output `EST`; otherwise it labels depth `ASSUMED`. This is not valid for arbitrary headlights. |
| Stereo road-camera path | **Code exists; hardware validation incomplete** | Stereo capture, calibration data structures, rectification, epipolar checking, and disparity ranging are present. A rigid calibrated pair, synchronization measurements, and range-accuracy results are still missing. |
| Camera calibration | **Backend present; operator workflow partial** | Checkerboard intrinsic and stereo-calibration functions exist, while the current wizard exposes only one-point driver and lamp references. Camera-to-windshield extrinsic calibration is not implemented. |
| Automated camera-related checks | **Small regression baseline passing** | Four tests pass for calibration profile construction/persistence and bright-core observation. They do not exercise physical cameras, exposure behaviour, timing, or metric accuracy. |

### 2.2 Camera challenges that currently limit the project

These are the main camera problems to make visible in demonstrations, reports, and
future design decisions:

| Priority | Challenge | Why it matters now | Evidence needed to close it |
|---|---|---|---|
| **Critical** | No measured camera-to-windshield transform | Camera-space values can look plausible while still placing the blocker at the wrong physical windshield location. | Calibrate rotation and translation for every installed camera, then measure centimetre error at known windshield targets. |
| **Critical** | General road-light depth is unobservable from one ordinary camera | Apparent lamp size changes with lamp design, intensity, exposure, focus, angle, weather, and distance. One reference lamp cannot represent real traffic. | Replace the current estimate with calibrated stereo, suitable RGB-D, or external range sensing and validate it at multiple distances. |
| **High** | Exposure and bright-source shape are unstable | Bloom, clipping, auto-exposure, reflections, and LED flicker change the detected centroid and diameter, corrupting both direction and range. | Record exposure state, mask/diameter stability, false selections, and error across controlled brightness and background conditions. |
| **High** | End-to-end timing is not measured | Driver frames and road frames are captured independently. With motion, even correct positions from different times produce a wrong ray intersection. | Timestamp capture, detection, geometry, and rendering; measure inter-camera skew and total latency; then add synchronization or prediction. |
| **High** | Driver depth depends on IPD and frontal pose | Incorrect IPD, yaw, glasses, partial eye visibility, or landmark jitter directly changes the estimated distance. | Compare estimates with measured ground truth at several depths and yaw angles, including glasses and blink recovery. |
| **High** | Calibration validity is not fully enforced | A saved profile can become invalid after changing resolution, camera device, mount, focus, threshold, lamp, or exposure behaviour. | Store and check device identity and all capture settings; reject mismatches and require recalibration after physical movement. |
| **High** | Binocular geometry stops at the tracking boundary | The camera worker provides two eyes, but midpoint-only geometry cannot guarantee that a physical blocker covers glare paths to both pupils. | Carry both eye coordinates through ray intersection, LCD mapping, confidence, and validation. |
| **Medium** | Camera health and confidence are incomplete | Connected/offline and FPS states exist, but the system has no unified confidence for stale frames, marginal landmarks, ambiguous lights, or calibration quality. | Add per-frame timestamps, confidence, dropout duration, stale-data rejection, and a fail-safe output state. |
| **Medium** | Hardware evidence is not yet reproducible | Current observations are useful but are not synchronized with ground-truth distances, video, configuration, and error logs. | Add CSV/video logging and repeat a fixed camera test matrix with measured positions and saved failure examples. |

The next camera milestone should therefore be a **measured and repeatable camera
subsystem**, not merely more visual features. The recommended order is:

1. Finish live regression of the current driver and road-camera pipeline.
2. Add timestamped CSV/video diagnostics and collect multi-position ground truth.
3. Expose full intrinsic calibration and reject incompatible camera profiles.
4. Implement camera-to-windshield extrinsic calibration.
5. Replace demonstration road ranging with a validated stereo or independent-depth
   solution.
6. Carry separate left/right-eye geometry through to the blocker output and measure
   total latency.

## 3. Coordinate system used by the software

The virtual windshield is the vertical plane `Y = 0`.

| Axis | Meaning | Sign convention |
|---|---|---|
| X | Horizontal/lateral | Negative left, positive right |
| Y | Depth | Driver behind windshield is negative; road light in front is positive |
| Z | Height | Zero at windshield bottom, positive upward |

Therefore:

- A driver distance of 50 cm is normally represented by approximately `Y = -50 cm`.
- A lamp distance of 200 cm is normally represented by approximately `Y = +200 cm`.
- The computed glare point lies on `Y = 0`.

## 4. Important measurement truth

### 4.1 Driver camera

A single driver camera can estimate depth because the real distance between the eyes
(IPD) supplies a known physical scale. The calibrated demonstration uses:

```text
driver depth = measured IPD × calibrated focal scale / observed iris separation
```

This estimate is affected by:

- inaccurate IPD or reference-distance measurement;
- head yaw and face angle;
- landmark error, glasses, reflections, or poor lighting;
- camera lens distortion;
- camera movement after calibration.

### 4.2 Road camera

A single image of a point light provides direction but not general absolute distance.
Intrinsic camera calibration alone cannot solve that missing scale.

For this controlled demonstration, the same lamp is first observed at a measured
reference distance. The system then uses the inverse change in its apparent bright-core
diameter:

```text
estimated range = reference distance × reference diameter / live diameter
```

This is only a demonstration estimate. It becomes invalid if the lamp, brightness
threshold, exposure response, viewing angle, focus, or camera position changes. Stereo
cameras, RGB-D, radar, LiDAR, or another independent scale source are required for
general road-light distance measurement.

## 5. Physical setup before every test

1. Mount camera 0 so the full face and both eyes remain visible.
2. Mount camera 1 firmly and point it toward the controlled lamp area.
3. Confirm Windows detects both cameras.
4. Close Camera, Teams, Zoom, browser video pages, and other programs using a webcam.
5. Keep the driver face evenly lit. Avoid strong light directly behind the driver.
6. Make the road-camera scene dim enough that the test lamp is the main bright object.
7. Remove mirrors, glossy objects, and direct reflections from the road-camera view.
8. Use a tape measure for all reference distances.
9. Measure distance from the camera lens plane, not from the laptop screen or tripod.
10. Do not move either camera after calibration.

## 6. Starting the application

Run:

```powershell
py -3.13 run.py
```

Initial configuration:

| Setting | Value |
|---|---|
| Driver camera | 0 |
| Headlight camera | 1 |
| Light Source | Manual initially |
| Detection Setup | Single Camera |
| Brightness threshold | 210 initially |
| Assumed depth | Actual approximate lamp distance before calibration |

Click **Start Session**.

Expected result:

- Driver preview becomes live.
- Camera status reports its backend and resolution.
- Iris markers appear when the face is visible.
- Header changes to `EYE TRACKING`.
- Eye telemetry shows X, Y, and Z.

## 7. Guided distance calibration

Open:

**Configuration -> Distance Calibration -> Guided Single-Camera Calibration**

The wizard automatically prepares driver camera 0 and road camera 1 in single-camera
mode.

### 7.1 Page 1: driver reference

Required measurements:

- Your IPD in centimetres. Use an optician's value if available.
- Straight distance from camera lens to the midpoint between your eyes.

Procedure:

1. Enter both measured values.
2. Sit in the normal demonstration position.
3. Face the camera directly and keep the head level.
4. Make sure both iris markers remain visible.
5. Hold still until at least 20 samples are available.
6. Select **Capture Stable Driver Reference**.
7. Repeat if the wizard reports unstable samples.

Pass condition:

- The page reports that the driver reference was saved.
- Variation is low, preferably below 3%; the wizard rejects variation above 8%.
- A focal-scale value is displayed.

### 7.2 Page 2: road-light reference

Required measurement:

- Straight distance from camera 1 lens to the front face of the test lamp.

Procedure:

1. Use the exact lamp or phone flashlight intended for the demonstration.
2. Enter the measured lens-to-lamp distance.
3. Point the lamp directly toward camera 1.
4. Keep it near the image centre.
5. Move it farther away if the preview reports `OVEREXPOSED`.
6. Remove any competing bright reflections.
7. Hold it still until at least 20 diameter samples are available.
8. Select **Capture Stable Road-Light Reference**.
9. Repeat if the wizard reports an unstable bright-core size.

Pass condition:

- The page reports that the road reference was saved.
- Diameter variation is low, preferably below 5%; the wizard rejects variation above
  12%.
- The saved summary includes reference diameter, scale, camera index, and threshold.

### 7.3 Page 3: review and activation

1. Read the displayed driver and road reference values.
2. Enable **Use calibrated IPD-based driver depth**.
3. Enable **Use reference-size road-light range estimate**.
4. Select **Finish**.

Expected result:

- Both calibration checkboxes become enabled in Configuration.
- Driver telemetry Y becomes a changing depth estimate.
- Road telemetry Y becomes a changing range estimate.
- Road-camera overlay displays `[EST]`.
- If road calibration is disabled, overlay displays `[ASSUMED]` and uses the Assumed
  depth control.

Calibration files are stored locally under `calibration/`. They are specific to the
user, cameras, and physical setup and are intentionally excluded from Git.

## 8. Functional test sequence

Perform tests in this order. Do not skip directly to the final intersection test.

### Test 1: application and camera startup

Action:

- Start the application and driver session.

Pass:

- No crash or camera-offline error.
- Camera 0 preview is responsive.
- Status includes backend and negotiated resolution.

### Test 2: driver landmark tracking

Action:

- Move the head left/right, up/down, closer/farther, and blink normally.

Pass:

- Iris markers follow both eyes.
- Tracking recovers after a blink.
- X and Z follow lateral and vertical movement.
- Calibrated Y changes smoothly with distance.

Fail indicators:

- Iris markers attach to glasses or eyebrows.
- Y changes significantly while the head is stationary.
- Tracking does not recover after a brief loss.

### Test 3: centre-reference calibration

Action:

- Sit normally, look forward, and select **Calibrate Center**.

Pass:

- Status reports calibrated.
- Returning to the same pose returns the marker near the same centre location.

Note: centre calibration removes a display offset. It is different from the guided
distance calibration and does not create metric camera coordinates by itself.

### Test 4: manual geometry

Action:

- Keep Light Source in Manual mode.
- Change light X, Y, and Z independently.
- Change windshield width and height.

Pass:

- 3D light marker and ray update.
- Intersection moves in the expected direction.
- 2D and 3D intersection displays agree.
- Out-of-bounds intersections are identified.

### Test 5: movement simulation

Action:

- Run Coming straight, Coming at the opposite side, and Long distance.

Pass:

- Each path is visually different.
- Ray and intersection update continuously.
- Stop restores normal interaction.

### Test 6: road light detection

Action:

- Change Light Source to Auto and Setup to Single Camera.
- Move the calibrated lamp slowly left/right and up/down.

Pass:

- Road preview remains at least 7 FPS on the current USB camera.
- Green circle stays on the intended light.
- Short missed detections do not cause rapid flicker.
- X and Z change smoothly.

If detection fails:

- Lower threshold by 10 at a time for a dim light.
- Raise threshold by 10 at a time if reflections are selected.
- Recalibrate road range after changing threshold.

### Test 7: road range estimate

Action:

- Put the lamp at its calibration distance.
- Then move it to two independently measured distances, one nearer and one farther.

Pass target for the demonstration:

- Estimated Y is close to the reference distance at the calibration point.
- Estimated Y increases when the lamp moves farther away.
- Estimated Y decreases when the lamp moves closer.
- Record percentage error at every measured position.

Use:

```text
percentage error = |estimated - measured| / measured × 100
```

Do not decide an acceptable accuracy after seeing the results. For the initial
demonstration, use a provisional target of no more than 15% error over the tested range.

### Test 8: driver depth estimate

Action:

- Test at the calibration position and at two independently measured positions.

Pass target for the demonstration:

- Eye Y magnitude follows measured lens-to-eye distance.
- Depth changes monotonically in the correct direction.
- Provisional target: no more than 10% error while facing forward.

Also repeat with modest head yaw to measure how much accuracy degrades.

### Test 9: end-to-end intersection

Action:

- Keep both cameras active.
- Hold the lamp fixed and move the head.
- Hold the head fixed and move the lamp.

Pass:

- Both independent movements change the intersection.
- Both previews remain live.
- No camera worker disconnects the other.
- Telemetry, 3D view, and 2D windshield remain consistent.

### Test 10: recovery and shutdown

Action:

- Hide the face briefly.
- Hide the lamp briefly.
- Switch Manual/Auto.
- Stop and restart the session.
- Close the application with both cameras active.

Pass:

- Tracking recovers without restarting the program.
- Camera devices reopen.
- Application exits without hanging.

## 9. Test record template

Create one row per run:

| Date/time | Test | Setup/positions | Expected | Observed | Error % | PASS/FAIL | Notes |
|---|---|---|---|---|---:|---|---|
| | Driver depth | | | | | | |
| | Road range | | | | | | |
| | Intersection | | | | | | |

Also record:

- camera names and indices;
- actual preview resolution and FPS;
- brightness threshold;
- driver IPD;
- all measured reference distances;
- room lighting;
- lamp type and orientation;
- whether either camera moved;
- screenshots or video of failures.

## 10. Troubleshooting guide

| Symptom | Likely cause | Action |
|---|---|---|
| Camera offline | Wrong index or device already open | Use driver 0/road 1; close other camera applications |
| Camera conflict | Same index assigned twice | Assign two different physical cameras |
| No iris samples | Face/eyes not visible or poor lighting | Face camera directly; improve even face lighting |
| Driver depth fixed | Guided profile disabled or invalid for current camera | Enable driver profile or recalibrate camera 0 |
| No bright-light samples | Threshold too high or lamp too dim | Lower threshold gradually; dim background |
| Wrong reflection tracked | Competing highlight or threshold too low | Remove reflection; raise threshold |
| Whole road frame white | Lamp too close/overexposed | Move lamp farther away; avoid pointing at very short range |
| Road distance fixed | Road profile disabled | Enable estimated road-light range |
| Road distance jumps | Bloom/exposure/angle changes | Stabilize lamp, scene, and threshold; recalibrate |
| `[ASSUMED]` displayed | Manual depth model active | Enable a valid camera-1 road profile |
| `[EST]` displayed but inaccurate | Profile used outside its valid setup | Restore same lamp/settings or recalibrate |
| Intersection appears plausible but wrong | Coordinate frames not physically registered | Complete intrinsic and extrinsic calibration before accuracy claims |

## 11. Current limitations that must remain visible

1. The road range is not a general single-camera measurement.
2. Guided calibration is one-point scale calibration, not full intrinsic calibration.
3. Camera-to-windshield rotation and translation are not calibrated.
4. Eye tracking currently uses the midpoint between both eyes for the ray calculation.
5. A physical blocker needs separate left-eye and right-eye rays.
6. No physical transparent/stripped LCD output is active.
7. No formal latency compensation or predictive filter is implemented.
8. No research CSV logger or synchronized ground-truth capture is implemented.
9. The final compatibility refactor and calibration workflow require extended hardware
   regression testing.
10. The current system must not be used as an automotive safety device.

## 12. Ordered development roadmap to the final goal

### Phase 1: freeze and validate the current demonstration

1. Complete all tests in Section 8.
2. Record accuracy at multiple driver and lamp distances.
3. Record detection FPS, dropouts, and recovery time.
4. Fix functional defects before redesigning the UI.
5. Use this workflow to remove, combine, or reorder confusing controls.

Exit condition: repeatable two-camera demonstration with documented accuracy and no
unexplained instability.

### Phase 2: redesign the operator UI around the workflow

1. Replace the long mixed controls panel with Setup, Calibrate, Run, and Validate stages.
2. Show camera assignments and connection health first.
3. Separate centre reference from metric distance calibration.
4. Show `ASSUMED`, `ESTIMATED`, or `MEASURED` beside every depth value.
5. Add calibration validity warnings when camera, threshold, resolution, or lamp changes.
6. Add a dedicated diagnostics page for FPS, exposure, threshold mask, and confidence.

Exit condition: a new user can complete setup and testing without reading source code.

### Phase 3: measurement-grade camera calibration

1. Add guided checkerboard intrinsic calibration for each camera.
2. Save distortion coefficients and validate reprojection error.
3. Add camera-to-windshield extrinsic calibration for rotation and translation.
4. Transform all eye and light coordinates into one measured windshield frame.
5. Add calibration age, camera identity, resolution, and quality metadata.
6. Reject incompatible or poor-quality profiles.

Exit condition: known 3D test points map to windshield coordinates within a predefined
centimetre error across the usable region.

### Phase 4: replace demonstration road ranging

Preferred options, in order of defensibility:

1. Calibrated stereo road cameras with rigid known baseline.
2. RGB-D/depth camera suitable for the required outdoor range.
3. Sensor fusion with vehicle/radar/LiDAR data.

Do not rely on lamp apparent size for arbitrary real vehicle headlights.

Exit condition: road-light depth is independently measured and validated, not inferred
from one lamp's appearance.

### Phase 5: binocular eye-to-light geometry

1. Preserve left and right eye coordinates independently.
2. Compute one ray per eye per light.
3. Compute separate windshield intersections.
4. Determine blocker size using pupil position uncertainty, optical spread, and latency.
5. Validate coverage while minimizing unnecessary blocked area.

Exit condition: both eyes are protected for all validated head positions.

### Phase 6: filtering, confidence, and latency

1. Add timestamped capture and synchronized processing measurements.
2. Add robust temporal filters or Kalman filters for eye, light, and intersections.
3. Reject outliers instead of smoothing them into valid tracks.
4. Predict short-term intersection motion to compensate end-to-end latency.
5. Propagate confidence from camera detections to blocker output.

Exit condition: stable output under realistic motion with measured latency and failure
behaviour.

### Phase 7: physical LCD blocker

1. Characterize the stripped LCD optical behaviour without backlight.
2. Implement a secondary-display renderer with a white/transparent background.
3. Render feathered black blocker spots at mapped LCD pixels.
4. Support all left/right-eye and multi-light spots.
5. Calibrate LCD pixel coordinates to physical windshield coordinates.
6. Measure opacity, spot size, response time, visibility, and thermal behaviour.

Exit condition: commanded physical spots align with measured ray intersections across
the tested windshield area.

### Phase 8: safety and research validation

1. Define fail-safe output for lost eyes, lost lights, stale frames, and camera failure.
2. Add synchronized CSV/video logging and ground-truth measurements.
3. Run repeatable static laboratory tests before any vehicle installation.
4. Test day/night lighting, glasses, multiple lights, occlusion, vibration, and heat.
5. Review automotive visibility, distraction, electrical, and mounting risks.
6. Obtain institutional/supervisor approval for any human or vehicle experiments.

Exit condition: documented evidence supports every performance and safety claim.

## 13. Definition of the final research prototype

The project should be considered a complete research prototype only when:

- all cameras are intrinsically and extrinsically calibrated;
- eye and light positions are validated in one physical coordinate frame;
- road-light depth is independently measured;
- both eyes receive separate blocker calculations;
- the physical LCD output is mapped and operating;
- latency, accuracy, stability, and recovery are measured;
- failure states remove or safely control the blocker;
- results are logged and repeatable;
- limitations are documented honestly.

Until then, the present system should be described as a **two-camera visualization and
controlled glare-intersection demonstration with approximate monocular depth aids**.
