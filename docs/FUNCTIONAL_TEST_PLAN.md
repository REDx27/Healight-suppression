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
| Automated regression suite | PASS | 11 tests cover mode/state policy, session transitions, profiles, and bright-spot observations |
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
3. Move closer and farther from the camera.

Pass criteria: iris markers remain on both eyes, the header reads EYE TRACKING,
and eye/target geometry moves without freezing.  Brief blinks may show NO FACE
but tracking must recover automatically.

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

1. Select **Driver Position Fixed**, choose **Single Camera**, and click **Run**.
2. Set driver camera `0`, headlight camera `1`, threshold `210`, and the measured
   light distance in Assumed depth.
3. Keep a phone flashlight one to three metres from camera 1 and move it slowly.
4. Observe the yellow diagnostic line in the road preview.

Pass criteria: preview rate is at least 7 FPS, a green circle follows the light,
Tracking bright light remains stable, and X/Z change smoothly.  If OVEREXPOSED
appears, move the lamp farther away.  If no circle appears, lower threshold in
steps of 10; if ordinary reflections are selected, raise it in steps of 10.

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
