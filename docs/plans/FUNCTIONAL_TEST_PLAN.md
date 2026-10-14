# GlareTracker Functional Test Plan

Use the source application (`py -3.13 run.py`) and record each result as PASS,
FAIL, or PARTIAL.  The current two-camera mapping is:

- Camera 0: integrated camera, driver/eye tracking
- Camera 1: USB camera, road/bright-light tracking

Do not assign the same camera index to both live workers.

## Current evidence

| Test | Status | Evidence |
|---|---|---|
| Dependency imports | PASS | OpenCV, MediaPipe, PyQt5, pyqtgraph, and OpenGL imported |
| Main window construction | PASS | Off-screen construction and visible launch succeeded |
| Camera discovery | PASS | Windows and OpenCV detected camera 0 and camera 1 |
| Driver frames and iris landmarks | PASS | 94 frames and 93 eye detections in 10 seconds |
| Road-camera throughput | PASS | Improved from 7 to 81 frames in 12 seconds at 640x480 MJPEG |
| Bright-source synthetic detection | PASS | Blank rejection, centroid accuracy, smoothing, and dropout hold passed |
| Automated regression suite | PASS | 27 tests cover mode/state policy, detected-camera assignment, raw preview integrity, zero-tuning lamp selection, immediate stale-track replacement, multi-scale clutter/window rejection, neutral saturated-lamp peak fallback, rejection of red-channel skin highlights, flare-resistant core centroiding, colored lights, static-background rejection, binocular/multi-light intersections, stable source IDs, tuning UI, profiles, and bright-spot observations |
| Physical road-light detection | PENDING | Requires the revised adaptive detector to be checked in the live preview |

## 1. Application and camera startup

1. Launch `run.py`.
2. Confirm the window opens without an exception.
3. Open Configuration, select **Headlight Position Fixed**, and set driver camera to `0`.
4. Click **Run**.

Pass criteria: the driver card identifies its backend and resolution, shows a
live image, and the header does not report CAMERA OFFLINE.

## 2. Eye tracking

1. Face camera 0 in even lighting.
2. Move left/right, then up/down.
3. Roll the head so one eye is visibly higher than the other.
4. Move closer and farther from the camera.

Pass criteria: iris markers remain on both eyes, the header reads BOTH EYES TRACKING,
and eye/target geometry moves without freezing. Head roll produces two vertically
separated windshield intersections for one light. Brief blinks may show NO FACE but
tracking must recover automatically.

## 3. Centre calibration

1. Look straight ahead from the intended driving position.
2. Click Calibrate Center.
3. Move away from centre and return to the same pose.

Pass criteria: status reports CALIBRATED and the returned centre is repeatable.

## 3A. Guided distance calibration

1. Open **Single-Camera Calibration → Calibrate Single-Camera Distances**.
2. Enter the measured driver IPD and camera-lens-to-eye distance.
3. Hold the driver's head straight and capture after 20 stable samples.
4. Place the demonstration lamp at a measured reference distance from camera 1.
5. Hold the lamp centred and steady, then capture after 20 stable diameter samples.
6. Review and activate both profiles.

Pass criteria: both pages reject unstable/insufficient samples, Finish enables both
profile checkboxes, driver telemetry Y changes when the driver moves closer/farther,
road telemetry Y changes inversely with apparent lamp size, and the road overlay changes
from `ASSUMED` to `EST`.

## 4. Manual light and intersection geometry

1. Select **Fully Manual** and click **Run**.
2. Change light X, Y, and Z individually.
3. Change windshield width and height.

Pass criteria: the light marker, ray, 2D intersection, 3D intersection, and
numeric readouts update consistently without moving the camera feeds.

## 5. Simulated light movement

In **Fully Manual** or **Headlight Position Fixed** while running, run each movement
preset and stop it midway.

Pass criteria: the light follows the selected path, the intersection follows
it, and stopping leaves the UI responsive.

## 6. USB road-light detection

1. Select **Stop**, then use **Refresh Available Cameras** in **Camera Selection**.
2. Select **Driver Position Fixed**, **Single Camera**, and choose the built-in webcam
   from the **Headlight camera** dropdown. The **Driver camera** selection is not opened
   in this mode.
3. Enter the measured light distance in **Assumed depth**, click **Standby**, then select
   **Load Daylight Phone-Light Preset**.
4. Choose **Multi-scale saliency** in the feed preview. The phone lamp should be the
   hottest compact region; broad illumination and long bright edges should be cooler.
5. Switch to **Detection overlay** and click **Run**. The isolated-phone preset accepts
   only the highest-ranked source, and the box reports its confidence.
6. Background capture is optional. If a stationary compact reflection still competes
   with the lamp, switch the phone off, select **Capture Background Without Test Light**,
   turn it on again, and inspect **Background difference**.
7. The preset disables and clears background rejection, selects the detection overlay,
   sets the saliency floor to 8, confidence to 25%, and maximum sources to one. A
   saturated-core fallback operates independently of the saliency threshold. Select
   **Peak-core mask** to verify that a fully exposed white source appears in white.

Pass criteria: preview rate is at least 7 FPS, a green circle follows the light,
the driver camera remains closed, tracking remains stable, and X/Z change smoothly. If OVEREXPOSED
appears, move the lamp farther away. Broad stationary lights must not be fixed by
arbitrarily raising the brightness threshold; verify the saliency, threshold-mask, and
background-difference stages to identify which rejection gate is responsible.

## 7. End-to-end two-camera operation

1. Select **Fully Auto**, choose **Single Camera**, and click **Run**.
2. Confirm eye tracking is active on camera 0 and road tracking on camera 1.
3. Move the driver's head, then move the light independently.

Pass criteria: both previews remain live and either movement updates the
windshield intersection without one camera disconnecting the other.

## 8. Recovery and shutdown

1. Switch from **Run** to **Standby** and confirm previews stay live while geometry freezes.
2. Click **Stop**, confirm both cameras are released, then click **Run** again.
3. Switch from **Fully Auto** to **Fully Manual** and back.
4. Close the application while both cameras are active.

Pass criteria: camera threads stop cleanly, devices reopen, and the process
exits without hanging.
