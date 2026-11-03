# GlareTracker Thesis and Design Reference

**Project:** Low-Cost Active Windshield Glare Suppression System
**Software:** GlareTracker v1.2 development source
**Original milestone snapshot:** 2026-10-05
**Consolidated through:** 2026-11-03
**Prepared for:** Project teammate and later thesis development
**Reviewed source baseline:** commit `e990901` plus the current guided-calibration working tree
**Current automated verification:** 107 tests passed on Python 3.13
**Document status:** Long-form design and milestone reference; current execution
status is maintained in `PROJECT_STATUS.md` and `docs/plans/VALIDATION_PLAN.md`.

> **Safety and research status:** This is a laboratory research prototype. It is not
> approved for installation or use in a moving vehicle. The current source includes an
> experimental secondary-display blocker, but the physical transparent LCD, installed
> coordinate mappings, latency, and fail-safe behavior remain unvalidated. Those tests
> must be completed before any safety claim is made.

---

## Document purpose

### Latest development decision — 2026-11-03

The operator confirmed **two road cameras plus the driver camera**. Single-road
light detection worked with a sunglass lens; the second road-camera feed became
live but stereo did not operate reliably. Accuracy is poor by observation, not yet
quantified. Camera availability is therefore no longer the known blocker, though
simultaneous operation of all three cameras remains to be validated.

The agreed next phase is rigid mounting, individual and stereo calibration,
then stationary-light tuning with Driver Position Fixed. Only after this road-pair
bring-up should live driver tracking and the remaining physical validation stages
resume. The new UI captures paired raw images, fits and gates calibration, archives
evidence, and saves ordered-camera/resolution-bound profiles. Stereo without a
compatible profile is preview-only; the assumed 900 px focal length / 25 cm baseline
fallback is removed. Per-camera candidate and match counts make tuning observable.
The first guided implementation now offers Calibrate/Skip after discovery and enforces
LEFT individual calibration, RIGHT individual calibration, then paired stereo fitting
with fixed intrinsics. Unrelated monocular/manual controls are hidden in stereo mode;
their workflows are preserved for regression and comparison. This first slice retains
the checkerboard path; ChArUco, post-filter verification, photometric comparison and
the broader interface reduction remain planned.

The 2026-11-03 live camera diagnosis identified a concrete enumeration and bandwidth
fault. Windows reported all three devices healthy, but the actual mapping was road
cameras 0 and 2 plus integrated driver camera 1. Two road streams at 640 x 480 could
open and grab while one returned no retrievable frames. At 320 x 240/15 FPS both road
cameras delivered every tested frame; all three cameras also delivered every tested
frame when the driver remained at 640 x 480/30 FPS. The software now applies this
measured mixed profile, verifies frames during discovery, and rejects the observed
ceiling fluorescent strip as an unsuitable point-source candidate.

An explicitly non-metric **ROUGH UNCALIBRATED** matcher is available only for camera
alignment and detector tuning before calibration. It pairs the controlled scene's
single candidate across both views and shows an assumed-depth marker, but is isolated
from windshield geometry, validity flags, diagnostic measurements and LCD output.
Color-bar/test-pattern frames are rejected and reported against the affected feed.

This is software preparation, not physical calibration completion. Ordinary USB
grabs are sequential, not hardware-synchronized. Fit-set errors do not prove
held-out distance accuracy; camera-to-windshield extrinsics remain unintegrated.
Use [the stereo setup guide](../guides/STEREO_CHESSBOARD_SETUP_GUIDE.md) for the next
bench session and [the validation plan](../plans/VALIDATION_PLAN.md) for completion
tracking. Earlier dated snapshots below remain development history.

This document is a detailed snapshot of the project from its initial idea to its
current implementation level. It combines the earlier workflow and test documentation
with the design decisions made during the latest development discussions. It is
intended to give a project teammate a clear update on the work completed so far and the
work that is continuing. It can later be used as a supporting reference when the final
thesis is written.

This is **not** a project handover, completion report, or final thesis. Features,
measurements, plans, and conclusions in this document must be updated as development
and physical testing continue.

The document helps the team understand:

1. why the system is being developed;
2. what has already been implemented;
3. how the current calculations work;
4. why particular hardware and software decisions were made;
5. which results are demonstrations rather than verified measurements;
6. what must still be built and tested; and
7. what evidence should be collected now for use in the later thesis.

The most important reporting rule is to separate **software functionality** from
**physical accuracy**. A feature may work correctly in the interface while still
requiring physical calibration and measured validation.

---

## 1. Executive summary

The research goal is to reduce direct headlight glare reaching a driver's eyes by
placing small dark regions on an LCD panel in front of the driver. The intended system
observes the driver's eyes and approaching headlights, calculates the straight-line
path between each light and each eye, and finds where those paths cross the LCD plane.
Those intersection locations become the required dark blocking regions.

The project deliberately targets a low-cost, tangible demonstration. Instead of using
industrial stereo cameras, LiDAR, radar, or an expensive depth camera, the planned
hardware uses inexpensive webcams mounted rigidly on a wooden frame, ordinary torch or
LED lights as simulated headlights, and an LCD-sized laboratory structure. The driver
sits behind the LCD plane while the lights face the driver from the other side.

The current software includes:

- real-time MediaPipe face and iris landmark tracking through legacy FaceMesh and
  current Tasks API compatibility paths, with a bundled model asset;
- separate left-eye and right-eye coordinates;
- a manual, single-camera, and stereo-capable road-light pipeline with independent
  multi-source candidates, stable IDs, confidence, and inspectable processing views;
- four explicit operating modes;
- Run, Standby, and Stop session states;
- guided one-point driver and lamp calibration for demonstrations;
- ray-to-windshield intersection calculation;
- separate intersections for every eye/light pair;
- a 3D scene, 2D windshield view, telemetry, and camera previews;
- temporal filtering for the road-light detector;
- asynchronous timestamped CSV/video research recording and pipeline timing;
- guarded camera-to-windshield extrinsic fitting and analysis tools;
- stale-sample rejection and fail-safe clearing;
- disabled-by-default experimental secondary-display blocker output; and
- 107 automated regression tests at the current milestone.

The current software does **not** yet provide a validated end-to-end glare-blocking
system. The main missing items are physical evidence and live calibration integration:

- physical chessboard calibration and measured road-stereo bring-up, followed by a
  clean ten-minute recording soak;
- stable and quantified driver-depth filtering;
- installed camera-to-windshield calibration applied by the live camera pipelines;
- physical stereo and multiple-lamp validation;
- ground-truth eye, lamp, and intersection measurements;
- externally measured photon-to-display latency and failure recovery;
- physical LCD mapping, attenuation, thermal, and safe-state validation;
- blocker-size derivation and overlap/coverage validation; and
- environmental and vehicle-like testing under the gated laboratory protocol.

The recommended budget strategy is to begin with one driver camera and two road
cameras. The wooden structure should include mounting positions for an optional second
driver camera. A second driver camera should be purchased and integrated only if
validation shows that the single-camera driver-depth error is too large. This staged
approach preserves the low-cost objective while leaving a technically stronger stereo
upgrade path.

---

## 2. Research problem and motivation

### 2.1 Problem statement

At night, light from an approaching vehicle can travel directly through the windshield
to the driver's pupils. The source can occupy only a small part of the driver's view,
but its brightness can cause discomfort, reduce contrast, produce temporary visual
impairment, and make road objects harder to see.

A conventional sun visor or uniformly tinted windshield blocks a large field of view.
The research hypothesis is that a dynamically controlled LCD can instead darken only
the small regions where the light rays pass through the windshield. The rest of the
display could remain transparent or minimally affected.

### 2.2 Main research question

Can a low-cost camera-based prototype estimate driver-eye and headlight positions well
enough to calculate and display localized glare-blocking regions on an LCD panel?

### 2.3 Supporting research questions

1. Can inexpensive webcams provide sufficiently stable eye and light positions in a
   controlled laboratory environment?
2. How much accuracy is lost when a single driver camera estimates depth using visible
   eye separation?
3. Does a second driver camera materially improve depth stability and final blocker
   placement?
4. Can two low-cost road cameras triangulate a simulated headlight accurately over the
   selected demonstration range?
5. How much end-to-end error comes from camera calibration, detection noise, timing,
   geometry, and LCD mapping?
6. How large must each blocking region be to cover measurement error and motion while
   avoiding unnecessary obstruction?
7. Can the required demonstration be produced within the project's limited hardware
   budget?

### 2.4 Project objectives

The project objectives are:

- produce a visible and understandable laboratory demonstrator;
- use affordable and replaceable hardware;
- track the two eyes independently;
- track one or more simulated headlights;
- express every observation in one LCD-relative coordinate system;
- calculate every eye-to-light intersection on the LCD plane;
- render the corresponding dark regions;
- quantify positional error, jitter, latency, and tracking availability; and
- document the difference between a successful demonstration and a road-ready system.

---

## 3. Evolution of the design and recorded team decisions

This section summarizes the important development conversations as engineering
decisions. It is not a word-for-word conversation transcript.

### 3.1 Initial software concept

The initial application represented one driver-eye point, one or more light positions,
a virtual windshield, and a ray-plane intersection. It demonstrated the central idea:
if the eye and light positions are known in the same coordinate system, their connecting
line determines the required blocking location.

The early prototype concentrated on visualization. This helped establish the geometry
and user interface, but the displayed coordinates were not yet measurement-grade.

### 3.2 Low-cost hardware became a primary requirement

An early hardware recommendation based on specialized stereo equipment exceeded the
available project budget by more than five times. The team clarified that affordable
hardware is not merely convenient; it is one of the research objectives.

The resulting decision was:

- use identical inexpensive webcams where possible;
- remove unnecessary plastic housings if required for compact mounting;
- mount cameras on one rigid wooden platform;
- keep the camera optical axes approximately level and parallel during construction;
- mechanically measure the camera baseline;
- represent headlights using controlled torches or LED sources;
- construct a frame close to the physical LCD dimensions; and
- perform the first experiments indoors under controlled lighting.

The important technical correction is that measured camera spacing alone is not enough.
Even carefully mounted cameras require intrinsic calibration, stereo calibration, and a
camera-to-LCD transform. Small mechanical alignment errors must be estimated by
calibration rather than assumed away.

### 3.3 Two separate webcams were preferred over an expensive dual-lens unit

A dual-lens camera may provide a rigid baseline and possibly synchronized capture, but
affordable models do not always expose two independent frames or provide calibration
data. Two identical ordinary webcams provide easier replacement and lower initial cost.

For the controlled demonstration, the chosen direction is therefore a rigid pair of
cheap, preferably identical webcams. Their limitations are accepted and measured:

- USB webcams are usually not hardware synchronized;
- auto-exposure may differ between units;
- actual frame rate may be below the advertised value;
- focus and lens distortion may differ even between identical models; and
- a flexible wooden or plastic mount can invalidate calibration.

### 3.4 The user interface was reorganized through live testing

Live testing revealed that starting a camera could cause the feed area to expand and
the 3D workspace to shrink. A later adjustment made the preview too small and gave it a
fixed horizontal allocation. The camera cards were then aligned from the left and made
resizable. Telemetry was moved beside the camera area and then structurally separated
from it so that it no longer behaved like part of a camera feed.

This evolution matters because it demonstrates iterative, user-led interface design:

1. detect an operational layout problem during a live camera run;
2. adjust the splitter and size policies;
3. observe the new problem created by over-constraining the feed;
4. restore resizing and left alignment; and
5. separate camera and telemetry responsibilities into sibling panes.

The current layout keeps the 3D workspace above, camera feeds in a lower left-aligned
strip, telemetry in a separate lower pane, and configuration in a right sidebar.

### 3.5 The midpoint-eye limitation was discovered

During single-camera testing, the driver rolled the head so that one eye was visibly
higher than the other. MediaPipe markers followed both irises, but the windshield view
kept the blocking points horizontally aligned. The reason was architectural: the
application collapsed the two landmarks into one midpoint before calculating the rays.

This could reduce blocking accuracy because a real head roll changes the position of
each pupil independently. The correction was to preserve both eye coordinates through
the entire geometry pipeline:

- the camera worker emits left-eye and right-eye coordinates;
- the tracking controller stores both positions;
- a separate ray is created from every light to every eye;
- the readout labels results by light and eye;
- the 3D view shows two eye points and multiple rays; and
- the windshield view shows the resulting separate intersection points.

A regression test now verifies that vertically separated eyes produce vertically
separated windshield intersections. This improvement has also been observed in live
testing. It is functionally implemented, but physical blocker coverage remains to be
validated.

### 3.6 Why two headlights and two eyes produce four blocking regions

For two headlights and two eyes, the direct-light paths are:

1. left headlight to left eye;
2. left headlight to right eye;
3. right headlight to left eye; and
4. right headlight to right eye.

Therefore, up to four intersection regions are geometrically correct. Some regions may
overlap or lie very close together. The final renderer should merge overlapping spots
into one larger region instead of drawing visually redundant shapes.

The current interface and automatic detector can represent multiple independent
sources with stable IDs, timestamps, confidence, and tracking states. Manual vehicle
layouts still use modeled offsets for simulation, but those offsets are not used by
automatic camera geometry. Physical two-lamp stereo correspondence and triangulation
remain unvalidated, so software multi-source support must not be reported as a passed
physical two-headlight experiment.

### 3.7 Driver-distance instability was identified

The user observed that the single-camera driver distance jumps forward and backward
even when the driver attempts to remain still. This is expected from the present
monocular method. Depth is inferred from the number of pixels between the irises, so a
small landmark change can produce a relatively large depth change.

The planned improvement is not to average the two eyes into one point. Instead, filtering
should operate on:

- the midpoint of the eyes, which describes head translation; and
- the eye-to-eye separation vector, which preserves horizontal and vertical head roll.

Recommended filtering includes an outlier gate, a short median window, an adaptive
low-pass or One Euro filter, stronger smoothing for depth than lateral movement, a
brief hold during lost frames, and immediate clearing after a safe timeout.

### 3.8 Optional stereo tracking on the driver side

The team considered adding two cameras on the driver side as well as two cameras on the
road side. Driver stereo can improve the weakest part of the current monocular driver
pipeline: absolute forward/backward distance. It can also improve independent 3D pupil
positions during translation and rotation.

The agreed budget-conscious strategy is:

1. continue initially with one driver camera;
2. stabilize and validate its measurements;
3. build the frame with mounting space for a second driver camera;
4. measure the remaining driver-position and blocker-position error; and
5. add a second driver camera only if the error exceeds the thesis target and the
   remaining budget permits it.

The current software does not yet implement driver-side stereo triangulation. Adding a
second driver camera later requires synchronized capture, stereo calibration, matching
the same left and right pupils between views, triangulation, and transformation into
LCD coordinates.

### 3.9 Low-cost camera compatibility was treated as an engineering result

The available cameras exposed an important practical constraint: a correct detector is
not useful when the capture path delivers frames too slowly. The first external-camera
trial produced about 7 frames in 12 seconds at its less compatible 1280 x 720 path.
Requesting a 640 x 480 MJPEG profile, using a small capture buffer, and trying
DirectShow, Media Foundation, then automatic OpenCV fallback improved a comparable run
to about 81 frames in 12 seconds. A driver-camera smoke test processed 94 frames and
reported eyes in 93 frames over 10 seconds.

These are engineering checkpoints, not statistically complete performance results.
Camera indexes 0 and 1 described the tested computer only; camera roles remain
operator-selectable because enumeration varies between computers and USB ports.

Python 3.13 also exposed a MediaPipe compatibility issue. The application now supports
the current Face Landmarker Tasks API while retaining the older FaceMesh route where
available. The model file is bundled at `assets/face_landmarker.task` so normal runtime
operation does not depend on downloading a model.

### 3.10 Bright-source detection evolved beyond a global threshold

Room testing exposed failure modes that a single intensity threshold could not solve:
bright windows, skin highlights, automatic exposure changes, saturated phone-lamp
cores, large halos, thin flares, coloured emitters, and stale tracks attached to old
clutter. The detector therefore evolved toward:

- strongest-channel intensity for coloured emitters;
- a weakest-channel neutral-core path for white sources;
- six-scale, eight-neighbour directional saliency;
- adaptive statistical segmentation;
- peak-core and distance-transform centre recovery for bloom and flares;
- configurable confidence, area, blur, morphology, source count, and ID distance;
- optional captured-background rejection; and
- stable identities with immediate replacement of a stale false single-source track.

A synthetic 640 x 480 benchmark recorded about 31.4 FPS at the detector milestone.
Synthetic tests and one-room observations demonstrate software behavior only; they do
not establish road-scene sensitivity or false-positive rates.

One especially useful physical observation was that a cheap sunglass lens placed over
the road camera made the phone flashlight substantially easier to isolate. Optical
attenuation may therefore be part of the sensing design rather than an incidental
accessory. However, a curved or tinted lens can introduce refraction, apparent-position
shift, internal reflection, colour bias, and distortion. Any final filter must be
identified, rigidly mounted, and included during intrinsic and camera-to-windshield
calibration. Moving or replacing it invalidates the relevant calibration. The control
values visible in the successful screenshot were one experimental condition, not
approved defaults; persistent named hardware/detection profiles remain future work.

### 3.11 Visual-design decisions were established through rejected alternatives

The UI was not produced in one styling pass. A blue-heavy design made cards difficult
to distinguish, while a later rainbow-coded semantic experiment looked inconsistent
and was rejected. The retained direction uses layered blue/green/neutral-gray surfaces,
spacing, and restrained borders, reserving warning and tracking colours for meaning.

The original dark 3D scene remains the preferred baseline. The optional light scene
uses a medium gray canvas (approximately `#c3c9cf`), not pure white, so the grids,
rays, markers, and labels remain visible. A fine minor grid and stronger major grid are
slightly separated to avoid depth fighting. Theme-specific marker colours and glow
treatments keep eyes, lamps, rays, and intersections visible in both modes. These are
usability decisions, not evidence of geometric accuracy.

### 3.12 A beginner-friendly calculation guide was produced

The repository contains an eight-page A4 landscape visual explanation at
`output/pdf/GlareTracker_Headlight_Calculations_Visual_Guide.pdf`, generated by
`scripts/generate_headlight_calculations_pdf.py`. It explains bright-point detection,
monocular direction, stereo disparity, coordinate transforms, ray-plane intersection,
and physical-to-pixel mapping using diagrams and small worked examples. The PDF was
rendered and visually inspected after formula-overflow corrections. It is an education
artifact that must follow the implementation; it is not experimental validation.

### 3.13 An exploratory web scene was not integrated

A separate chat produced a conceptual React Three Fiber/Vite driver-view scene in a
temporary `Simulations\\2nd` workspace. It explored a full-screen night scene, a
semi-transparent slanted windshield, road grid, driver viewpoint, and constrained orbit
controls. Dependency installation and browser verification did not complete, the
temporary workspace is no longer present, and no React source or `package.json` exists
in this repository. The experiment is therefore recorded only as discarded/external
design exploration, not as an implemented GlareTracker feature. Its presentation
constants were never physical calibration values.

### 3.14 Verified development checkpoints

Repository history provides the following useful implementation anchors:

| Commit | Milestone |
|---|---|
| `26d34dc` | Selectable camera-based headlight tracking |
| `15a3f03` | Modern operator dashboard architecture |
| `1ad6f5b` | Dashboard visual and runtime-efficiency refinements |
| `fd4a36e` | Vector icons and modernized 3D visualization |
| `074b2d0` | Ribbon controls and responsive navigation |
| `8078b0f` | Rejected semantic/rainbow theme experiment |
| `bd0f101` | Cohesive simulation-studio theme |
| `782d7ca` | Stabilized camera tracking and documented v1.2 baseline; pushed to `origin/master` |
| `26aed1c` | Operating modes and guided demonstration calibration; current local `master` |

The current working tree contains substantial later validation, logging, extrinsic,
LCD, detector, and documentation work that has not yet been committed. A commit hash
therefore identifies a historical checkpoint, not the complete present state.

---

## 4. Intended physical demonstrator

### 4.1 Minimum planned configuration

| Component | Quantity | Purpose |
|---|---:|---|
| Laptop or desktop computer | 1 | Runs detection, geometry, visualization, and LCD output |
| Driver-facing webcam | 1 | Detects face and both iris centers |
| Road-facing webcams | 2 | Stereo observation of simulated headlights |
| LCD panel or monitor | 1 | Represents the glare-blocking plane |
| Torch or LED sources | 2 | Simulate a two-headlight vehicle |
| Rigid wooden frame | 1 | Holds LCD and cameras in a repeatable geometry |
| Printed checkerboard | 1 | Camera intrinsic and stereo calibration |
| Tape measure/ruler | 1 | Reference distances and construction measurements |
| Fixed artificial-eye target | 1 | Repeatable ground truth without human movement |

### 4.2 Optional expanded configuration

Add a second driver-facing webcam. The complete system would then use four cameras:

- two driver cameras for stereo 3D eye positions; and
- two road cameras for stereo 3D headlight positions.

This is expected to improve driver depth but also increases calibration work, USB
bandwidth, processing load, and synchronization requirements.

### 4.3 Recommended frame properties

- Use a thick, braced panel rather than a flexible strip of wood.
- Add fixed mounting holes, slots, or printed brackets so camera positions can be
  restored after removal.
- Record each baseline from the lens center, not the outside of the camera case.
- Make camera yaw, pitch, and roll adjustable during setup, then lock them.
- Mark the LCD center, edges, and coordinate origin physically.
- Include mounting points for the optional second driver camera from the beginning.
- Prevent the frame from being moved between calibration and data collection.
- Photograph the final frame with labeled dimensions for the thesis.

### 4.4 A stereo pair does not need to become one visual image

For stereo calculation, the program should retain two separate images. It finds the
same object in both frames and uses the horizontal displacement between them to
calculate depth. A combined side-by-side preview may be shown to the operator, but
merging the images into one photograph is not the measurement goal.

---

## 5. Coordinate system and physical meaning

The software models the LCD/windshield as the vertical plane `Y = 0`.

| Axis | Meaning | Convention |
|---|---|---|
| X | Horizontal position | Negative left, positive right |
| Y | Depth | Driver behind panel is negative; lights in front are positive |
| Z | Height | Zero at panel bottom; positive upward |

Example positions:

- a driver eye 50 cm behind the panel may have `Y = -50 cm`;
- a simulated headlight 200 cm in front may have `Y = +200 cm`;
- an LCD intersection always has `Y = 0 cm`.

All driver cameras, road cameras, and LCD pixels must eventually refer to this same
physical coordinate frame. At present, parts of the system approximate that alignment.
The camera-to-windshield transform and the separate LCD-to-windshield pixel mapping are
therefore critical accuracy tasks. Software fitting tools exist, but the installed
physical transforms have not yet passed validation or been applied by the live camera
pipelines.

---

## 6. Current application initialization and runtime process

### 6.1 Application initialization

When the application starts:

1. Qt creates the main event loop and high-DPI settings.
2. `MainWindow` creates the header, 3D workspace, 2D windshield view, camera cards,
   telemetry panel, and configuration controls.
3. The `TrackingController` is connected to the 3D view, windshield view, telemetry,
   and controls.
4. Driver and road camera workers are configured but remain stopped.
5. Saved demonstration calibration profiles are loaded when compatible.
6. The session begins in **Stop**, so cameras are released and calculations are idle.

### 6.2 Operator selects an operating mode

The selected mode defines which positions are obtained from cameras and which are
entered manually.

| Mode | Driver source | Headlight source | Primary use |
|---|---|---|---|
| Fully Auto | Driver camera | Road camera(s) | End-to-end live demonstration |
| Fully Manual | Manual coordinates | Manual coordinates | Geometry and UI testing without cameras |
| Driver Position Fixed | Manual coordinates | Road camera(s) | Isolate road-light tracking |
| Headlight Position Fixed | Driver camera | Manual coordinates | Isolate driver-eye tracking |

Controls that are irrelevant to the selected mode are disabled. This prevents an
operator from believing that a manual value affects a camera-controlled calculation.

### 6.3 Operator selects a session state

| State | Camera behavior | Calculation behavior |
|---|---|---|
| Run | Required cameras active | New coordinates and intersections accepted |
| Standby | Required previews remain active | Geometry is frozen |
| Stop | All cameras released | Tracking and calculated output cleared |

**Run** is for active experiments. **Standby** is for safely positioning the driver,
lights, or cameras while retaining previews. **Stop** ends the session and releases the
devices so another application or configuration can use them.

### 6.4 Driver-camera processing loop

For every available frame:

1. OpenCV captures an RGB image.
2. MediaPipe detects one face and refined facial landmarks.
3. The program reads the left and right iris centers.
4. Optional head-pose estimation calculates pitch, yaw, and roll.
5. The active calibration path converts both iris centers to approximate centimetres.
6. The camera thread emits the two eye positions and an annotated preview.
7. During Run, the tracking controller accepts the positions.
8. During Standby, the preview continues but the controller ignores new geometry.

### 6.5 Road-camera processing loop

In single-camera mode:

1. capture one frame;
2. create a strongest-channel intensity image so white, amber, red, and blue emitters
   are not penalized by grayscale channel weights;
3. compare every central patch against all eight surrounding patches at six scales;
4. combine the strongest scale responses into a directional saliency map;
5. segment that map with a scene-adaptive mean-plus-standard-deviation threshold and
   the configured minimum saliency floor;
6. combine saliency with adaptive brightness and, when enabled, an exposure-compensated
   captured-background difference;
7. clean the binary mask and score candidates using saliency, brightness, compactness,
   area, and saturated-core evidence;
8. reject low-confidence clutter and rank the remaining independent sources;
9. estimate a weighted center and apparent diameter;
10. assign stable IDs, smooth observations, and briefly bridge dropouts;
11. calculate a direction and use an assumed or demonstration-estimated distance; and
12. emit the light positions and inspectable processing previews.

This multi-scale local-contrast approach was selected instead of a trained object
detector because the target is an optical emitter rather than a fixed semantic object,
the system must accept motorcycles, cars, torches, and colored lamps, and no labeled
project dataset currently exists. The method follows the established small-bright-target
principle of comparing a candidate patch with its neighborhood at multiple scales. A
single-scale top-hat or Gaussian subtraction remains vulnerable when the apparent lamp
diameter changes, as occurred in the close phone-light test.

In stereo mode:

1. request near-simultaneous frames from the two road cameras;
2. detect a bright point in each image;
3. rectify the image points when calibration data exists;
4. check that the points approximately satisfy the epipolar constraint;
5. calculate disparity and triangulated depth;
6. smooth the resulting 3D position; and
7. emit separate previews and the light position.

### 6.6 Geometry and display update

For every accepted set of eyes and lights:

1. create every eye/light pair;
2. calculate the line from that eye to that light;
3. find where the line crosses `Y = 0`;
4. test whether the intersection lies within the configured panel dimensions;
5. update the eye, light, ray, and intersection objects in the 3D scene;
6. convert valid intersections into normalized windshield positions;
7. update the 2D front view; and
8. update labeled telemetry such as `L1/E1` and `L1/E2`.

---

## 7. System architecture

### 7.1 Main components

```text
Qt main thread
  MainWindow
    Application header and Run/Standby/Stop controls
    Operating/configuration controls
    Driver and road camera preview cards
    3D scene, 2D windshield, and telemetry
    TrackingController

Driver QThread
  OpenCV capture
  MediaPipe face/iris detection
  Optional head pose and monocular depth
  Left/right eye signals

Road QThread
  Single-camera bright-source detection
  OR two-camera stereo bright-source triangulation

TrackingController
  Centre-reference offset
  Eye/light pairing
  Ray-plane intersections
  3D, 2D, and telemetry updates
```

### 7.2 Important files

| File | Responsibility |
|---|---|
| `glare_tracker/app.py` | Qt application startup |
| `glare_tracker/window.py` | Window composition, state transitions, and signal wiring |
| `glare_tracker/operating_modes.py` | Four operating modes and three session-state policies |
| `glare_tracker/camera.py` | Driver capture, MediaPipe, head pose, and eye coordinates |
| `glare_tracker/headlight_detector.py` | Single/stereo road-light detection and filtering |
| `glare_tracker/calibration.py` | Intrinsic, stereo, and demonstration profile structures |
| `glare_tracker/geometry.py` | Unprojection, depth estimation, ray intersection, LCD mapping |
| `glare_tracker/tracking.py` | Per-eye/per-light business logic and visualization updates |
| `glare_tracker/widgets/scene_3d.py` | 3D eyes, lights, rays, windshield, and intersections |
| `glare_tracker/widgets/windshield_2d.py` | Front-view intersection display |
| `glare_tracker/widgets/readout.py` | Telemetry and labeled intersection results |
| `glare_tracker/widgets/controls.py` | Modes, dimensions, camera indices, and manual positions |
| `glare_tracker/widgets/calibration_wizard.py` | Guided one-point demonstration calibration |
| `tests/` | Automated regression tests |

### 7.3 Why camera work runs outside the UI thread

Camera capture and MediaPipe/OpenCV processing can take longer than one display update.
Running them in worker threads prevents the application window from freezing. The
workers emit Qt signals containing copied images and numeric observations. The main Qt
thread then updates the widgets safely.

---

## 8. Algorithms explained for the thesis

### 8.1 Detecting the two eyes

MediaPipe provides facial landmarks, including refined iris landmarks. The program
averages the landmark points around each iris to obtain one image coordinate for the
left iris and one for the right iris.

The central design improvement is that these points are no longer discarded after a
midpoint is calculated. Both eyes continue independently through the geometry pipeline.
The midpoint remains useful for head translation and center calibration, while the
vector between the eyes represents separation and head roll.

### 8.2 Single-camera driver depth

The guided driver calibration uses the person's measured interpupillary distance (IPD)
as a known physical scale. In simple form:

```text
estimated depth = real IPD * focal length in pixels / observed IPD in pixels
```

If the eyes appear closer together in the image, the person is estimated to be farther
away. If they appear farther apart, the person is estimated to be closer.

The current code includes a yaw correction because turning the face makes the visible
eye separation look smaller. Even with that correction, the result can change because
of landmark jitter, glasses, blink state, inaccurate personal IPD, camera distortion,
or a non-frontal pose.

The uncalibrated fallback does not measure depth. It maps eye pixels across the
configured panel dimensions and uses a fixed manual eye distance.

### 8.3 Why monocular depth jumps

Depth is inversely related to observed eye separation. When the eye separation is only
dozens of pixels, a one- or two-pixel landmark change can noticeably alter the depth.
This is why lateral and vertical tracking may look stable while forward/backward depth
jumps.

The next filter should preserve real head motion while reducing stationary noise:

```text
raw left/right eyes
  -> reject anatomically impossible samples
  -> calculate midpoint and eye-separation vector
  -> short median filter
  -> adaptive low-pass filter
  -> reconstruct filtered left/right eyes
  -> calculate intersections
```

Depth should normally receive stronger smoothing than X and Z. Filter delay must be
measured because excessive smoothing can cause blockers to lag during head movement.

### 8.4 Single-camera road-light estimation

One ordinary camera provides the direction of a bright source, but a point in one image
does not reveal its absolute distance. The current demonstration offers two choices:

- use an operator-entered assumed distance; or
- estimate distance from the apparent bright-core diameter of the same calibrated
  torch at a known reference distance.

The demonstration relationship is:

```text
estimated distance = reference distance * reference diameter / live diameter
```

This estimate is valid only under controlled conditions. Bright-core size changes with
lamp design, exposure, bloom, focus, angle, and threshold. It must not be presented as
general real-vehicle headlight ranging.

#### 8.4.1 Bright-source candidates, confidence, and identity

The current road detector does more than threshold grayscale intensity. It creates
intermediate strongest-channel, neutral-core, blurred, saliency, local-contrast,
background-difference, threshold, and peak-core images. Contours from the accepted
masks become candidates with centre, diameter, area, confidence, bounds, and detection
method. Confidence and area gates remove weak candidates, while a temporal
`LightSourceTracker` assigns stable IDs, smooths positions, briefly tolerates dropout,
and replaces stale clutter when a new dominant source appears elsewhere.

This architecture separates vehicle interpretation from optical detection. A
motorcycle-like test can request one source, while a multi-lamp experiment can request
more, without encoding fixed car-headlight spacing in the automatic detector.

### 8.5 Road stereo triangulation

Two cameras view the same bright source from positions separated by a known baseline.
After stereo calibration and rectification, a nearby point appears at different
horizontal positions in the two images. This difference is disparity.

```text
depth = focal length * camera baseline / disparity
```

Large disparity usually means the light is closer. Small disparity means it is farther
away. Reliable triangulation requires:

- correct intrinsic calibration for each camera;
- stereo rotation and translation calibration;
- a rigid baseline;
- the same light matched in both frames;
- sufficient image resolution and disparity;
- limited time difference between frames; and
- a transform from the stereo rig into the LCD coordinate system.

The current calibrated stereo code contains rectified-point matching (vertical error
at most 3 px), positive-disparity depth and temporal smoothing. As of 2026-10-27,
uncalibrated stereo produces previews only. Camera order and frame resolution must
match the saved profile. The simplified rig-to-world mapping is still an approximation
until installed camera-to-windshield transforms are integrated and measured.

### 8.6 Ray-to-panel intersection

Let an eye position be `E = (Ex, Ey, Ez)` and a light position be
`L = (Lx, Ly, Lz)`. A point along the line is:

```text
P(t) = E + t * (L - E)
```

The LCD plane is `Y = 0`. The value of `t` at the panel is:

```text
t = -Ey / (Ly - Ey)
```

The panel position is then:

```text
intersection X = Ex + t * (Lx - Ex)
intersection Z = Ez + t * (Lz - Ez)
intersection Y = 0
```

The software rejects a parallel line or a crossing outside the segment between the eye
and light. It then checks whether X and Z fall inside the physical panel boundaries.

### 8.7 Number of required blockers

For `E` tracked eyes and `L` independently tracked lights, the maximum number of direct
paths is:

```text
number of paths = E * L
```

For two eyes and two headlights, the maximum is four. For two eyes and eight detected
lights, the maximum is sixteen. The current detector and 3D scene support up to eight
independent sources; the operator can reduce that limit in the detection-tuning panel.

### 8.8 Converting a physical intersection to an LCD pixel

The geometry module already contains the basic mapping from a physical panel location
to a pixel coordinate. The physical panel width and height are scaled to its pixel
resolution, and the vertical axis is inverted because image pixels usually count down
from the top.

The source now contains an experimental secondary-display renderer with explicit
display selection, full-screen output, configurable radius, feathered black spots, and
white fail-safe clearing. It remains disabled by default. Physical LCD-to-windshield
mapping, overlap/coverage policy, optics, latency, temperature, power/signal failure,
and actual transparent-state behavior remain unvalidated.

### 8.9 Blocker radius

An infinitely small calculated point is not sufficient in practice. A blocker must
cover:

- the apparent angular size of the light;
- the pupil area and small eye movement;
- camera and calibration error;
- frame-to-frame jitter;
- motion during total system latency; and
- a deliberate safety margin.

A defensible experimental rule is to choose a radius larger than the measured 95th
percentile intersection error plus estimated motion and source-size margins. The thesis
should report the resulting blocked screen area as well as coverage success.

---

## 9. Feature and implementation status

### 9.1 Status definitions

| Status | Meaning |
|---|---|
| Implemented | Present in source and covered by software or live functional evidence |
| Partial | Main code exists, but calibration, validation, or complete workflow is missing |
| Demonstration only | Useful in the controlled prototype but not physically generalizable |
| Planned | Agreed requirement without a finished implementation |

### 9.2 Current feature matrix

| Feature | Status | Current evidence or limitation |
|---|---|---|
| Qt desktop application | Implemented | Launches with operator dashboard and responsive panes |
| Run/Standby/Stop | Implemented | State policy and automated session tests exist |
| Four operating modes | Implemented | Camera/manual source policy is explicit and tested |
| Driver camera capture | Implemented | Windows backend fallback and 640x480 MJPEG configuration |
| MediaPipe face/iris tracking | Implemented | Both irises visible in annotated live preview |
| Separate left/right-eye geometry | Implemented | Independent rays/intersections and head-roll regression test |
| Single-camera driver depth | Demonstration only | IPD-based estimate works but remains noisy and unvalidated |
| Driver temporal stabilization | Planned | No dedicated binocular eye filter yet |
| Driver stereo tracking | Planned optional upgrade | No stereo driver worker or pupil triangulation yet |
| Manual light position | Implemented | X/Y/Z input and simulated movement paths |
| Single road-camera detection | Implemented | Multi-candidate bright-region detector, stable IDs, confidence/state records, and tunable previews |
| Single road-camera range | Demonstration only | Assumed depth or calibrated same-lamp apparent-size estimate |
| Stereo road pipeline | Partial | Multi-candidate epipolar matching and triangulation exist; physical accuracy pending |
| Independent multiple-light detection | Implemented in software | Variable source list, stable IDs, timestamps, confidence and tracking states; physical multi-lamp validation pending |
| Custom road-camera tuning | Implemented | Optional exposure/brightness/contrast/gain plus brightness, saliency, confidence, background-change, area, blur, cleanup, source-count, and ID-distance controls; a daylight phone-light preset provides a repeatable starting point |
| Processing-stage previews | Implemented | Each road feed can show detection overlay, original, final candidate mask, background difference, multi-scale saliency, local contrast, strongest-channel intensity, or blurred intensity |
| Broad-light and clutter rejection | Implemented in software | Six-scale eight-neighbor contrast suppresses broad illumination and long edges, while confidence ranks saturated core/halo sources above weaker clutter; synthetic screenshot-like coverage passes |
| Controlled-scene background rejection | Implemented | Captured reference frame removes stationary bright regions such as a nearby window while retaining newly introduced test lights |
| Camera-control readback | Implemented | Requested exposure is compared with camera-reported values so unsupported webcam controls are visible |
| Detected-camera role assignment | Implemented | Refreshable dropdowns list available devices with index, resolution, and backend; fixed-driver mode opens only the selected headlight camera |
| Modeled car/multi-light layout | Manual visualization only | Fixed offsets remain available for manual simulation but are not used by automatic camera geometry |
| Ray-plane intersection | Implemented | Pure geometry function and multi-eye integration |
| 3D scene | Implemented | Two eyes, up to eight lights, rays, and up to sixteen hits |
| 2D windshield view | Implemented | Separate normalized glare points and bounds state |
| Separate telemetry pane | Implemented | Eye coordinates and labeled light/eye intersections |
| Guided driver/lamp calibration | Partial | Stable one-point demonstration profiles, not full metric installation |
| Intrinsic/stereo chessboard workflow | Software implemented for road pair | Startup Calibrate/Skip plus ordered LEFT, RIGHT and paired capture; fixed-intrinsic stereo gates and profile loading; physical/filter validation and standalone driver intrinsic UI remain |
| Camera-to-windshield extrinsics | Software ready; physical integration pending | Rigid transforms, solvePnP fitting, held-out validation, compatibility guards, and a CLI exist; no installed profile has passed and the live pipelines do not yet apply one |
| LCD blocker output | Experimental software implemented | Disabled-by-default secondary-display window renders feathered spots and clears to white; stripped-panel validation is pending |
| Blocker merging and sizing | Planned | Needed for overlapping paths and real coverage |
| Prediction/latency compensation | Planned | No end-to-end predictor yet |
| CSV/video research logging | Implemented in source | Asynchronous telemetry, video, frame sidecars, metadata, timing, and shutdown flushing are tested; the ten-minute dual-camera soak is pending |
| Timing and stale-data protection | Implemented in source | Capture/detection/GUI/geometry/preview timestamps and a 250 ms stale-sample guard exist; physical deadlines are not validated |
| Standalone build pipeline | Partial | Build scripts exist; latest source requires packaging validation |

### 9.3 Current automated evidence

The detector-era checkpoint contained twenty-seven tests covering:

- operating-mode policy;
- camera requirements by mode;
- Run/Standby/Stop transitions;
- main-window session behavior;
- calibration-profile logic;
- bright-source observation behavior; and
- binocular intersection geometry, including vertically separated eye points;
- independent multi-light candidate detection;
- stable light identity when brightness ordering changes; and
- camera geometry consuming the detected source list without vehicle offsets; and
- custom detection-panel and feed-preview control availability; and
- detected-camera dropdown assignment with the driver-camera role inactive; and
- unmodified output from the Original camera-preview mode; and
- rejection of a static bright window while retaining a newly introduced light; and
- multi-scale rejection of a broad bright window while retaining a compact phone light;
- ranking of a large saturated lamp and halo above broad illumination, long edges, and
  weaker compact clutter; and
- detection of colored emitters through strongest-channel intensity; and
- saturated-core recovery when the directional saliency gate alone is too strict; and
- distance-transform centroid recovery when a saturated core is connected to a thin
  flare or bright streak; and
- neutral multi-channel selection of white emitters over skin highlights that saturate
  only the red camera channel;
- lamp-over-nose selection using untouched startup defaults; and
- immediate replacement of a stale false single-source track when the lamp appears at
  a different image position.

The current Python 3.13 suite contains **107 passing tests**, including synthetic stereo
fitting with supplied individual intrinsics, startup prompt policy, staged workflow,
profile compatibility, calibrated matching, and mocked capture/UI paths.
Earlier coverage adds geometry
boundaries, timestamped telemetry/video, ground-truth analysis, rigid transforms,
guarded extrinsic fitting, physical-intersection error decomposition, latency and stale
rejection, LCD fail-safe behavior, and the earlier session/detector cases. These tests
protect software behavior. They do not replace physical-camera accuracy, timing,
lighting, and LCD experiments.

### 9.4 Recorded live evidence

Previous controlled observations include:

- 94 driver frames and 93 eye detections during one 10-second run;
- improvement of a tested USB road camera from 7 to 81 frames in 12 seconds after
  switching to a lower-bandwidth MJPEG profile; and
- live confirmation that independent eye intersections now respond to head roll;
- a synthetic 640 x 480 detector benchmark of about 31.4 FPS; and
- one room test in which a sunglass lens over the road camera materially improved
  phone-flashlight isolation.

These are engineering observations, not a statistically complete evaluation. The final
thesis should replace isolated values with repeated trials, settings, ground truth, and
confidence intervals or descriptive variation. In particular, the filter observation
must be repeated with a fixed documented mount and calibrated final optics.

---

## 10. Calibration hierarchy

Calibration should be explained as several different tasks. Completing one does not
automatically complete the others.

### 10.1 Center-reference calibration

The **Calibrate Center** button records the current eye midpoint as a display reference
and applies a common offset. It is useful for aligning the visualization with the
operator's normal pose. It does not measure lens distortion or the physical camera
pose.

### 10.2 Guided driver-distance calibration

The current wizard records:

- measured driver IPD;
- measured camera-lens-to-eye distance; and
- stable iris-separation samples.

It estimates a focal scale for the monocular IPD depth relationship. This is a
single-person, single-setup demonstration calibration.

### 10.3 Guided road-lamp calibration

The wizard records:

- a known camera-to-lamp reference distance;
- the detected bright-core diameter;
- camera index, image size, and brightness threshold; and
- stability over a short sample window.

It is valid only for the same controlled lamp and capture behavior.

### 10.4 Intrinsic calibration

Each camera needs images of a known checkerboard at different positions and angles.
Intrinsic calibration estimates focal lengths, principal point, and lens distortion.
The backend exists in `calibration.py`. The road-pair chessboard dialog now captures
and fits LEFT and RIGHT independently, archives both results, and only then enables
the paired stereo stage. A standalone full intrinsic calibration UI for the driver
camera remains outside this workflow.

### 10.5 Stereo calibration

A camera pair observes the same stationary checkerboard in paired images. Stereo calibration
estimates the rotation and translation between the two cameras and enables
rectification. Separate stereo calibration is needed for the road pair and, if added,
the driver pair. The road-pair dialog requires at least 15 varied captures, gates
stereo RMS and rectified row error, and preserves raw pairs plus a fit report. Capture
uses sequential grabs; no exposure synchronization or physical accuracy is claimed.

### 10.6 Camera-to-windshield extrinsic calibration

This estimates how every installed camera rig is rotated and translated relative to
the windshield origin and axes. The current source provides rigid transforms,
solvePnP-based fitting, held-out target validation, profile persistence, intrinsic
fingerprinting, and compatibility checks. No installed camera has yet passed the
physical target matrix, and the live camera pipelines do not yet apply these profiles.
Without that integration, the program may calculate internally consistent but
physically misplaced blockers.

The completed system should transform every measured point as:

```text
point in windshield coordinates = rotation * point in camera coordinates + translation
```

The transformation must be re-established after a camera, windshield/LCD, filter, or
mount is moved. LCD pixels then require a separate LCD-to-windshield mapping.

---

## 11. Major technical challenges

### 11.1 Driver-depth noise

**Cause:** monocular depth is highly sensitive to small iris-landmark changes.
**Effect:** the intersection moves even when the driver is nearly stationary.
**Next action:** implement and tune a binocular-preserving temporal filter, then measure
stationary jitter and moving response.

### 11.2 Lack of a shared physical coordinate system

**Cause:** installed camera-to-windshield rotations and translations have not been
physically measured, passed, and applied by the live pipelines.
**Effect:** virtual points cannot yet be claimed as accurate physical windshield/LCD
positions.
**Next action:** complete the held-out target protocol, then integrate only compatible
passing profiles into the live pipelines.

### 11.3 Multiple physical headlights

**Cause:** multiple candidates and stable identities exist in software, but physical
multi-lamp stereo association has not been validated.
**Effect:** two real torches cannot yet be claimed as independently and accurately
triangulated.
**Next action:** use a rigid calibrated road pair to validate candidate correspondence,
crossing, dropout, ambiguity rejection, and physical 3D error.

### 11.4 Cheap-camera synchronization

**Cause:** ordinary webcams capture and deliver frames independently.
**Effect:** moving lights or eyes may be observed at different times, creating a false
3D position.
**Next action:** timestamp capture/processing, measure skew, prefer stable frame rates,
and add prediction or software synchronization if required.

### 11.5 Exposure, bloom, and reflections

**Cause:** bright torches saturate pixels; webcams change exposure automatically; shiny
surfaces can create competing bright regions.
**Effect:** the detected center and apparent size shift, corrupting direction and
single-camera range.
**Next action:** use a controlled scene, matte surroundings, fixed exposure where
supported, overexposure warnings, and tests at several brightness levels. Evaluate the
filter-assisted camera path with a rigid documented filter mount and recalibrate with
the final optics installed.

### 11.6 Tracking loss and confidence

**Cause:** blinks, head turns, occlusion, glasses, frame drops, or an obscured light.
**Effect:** stale blocker coordinates could remain visible or move incorrectly.
**Current software guard:** confidence/state records, source timestamps, a 250 ms
freshness limit, and fail-safe clearing exist.
**Next action:** execute the physical failure-injection matrix and prove that the actual
panel reaches its transparent safe state within the declared deadline.

### 11.7 Latency

**Cause:** exposure, USB delivery, detection, geometry, Qt updates, and LCD refresh each
add delay.
**Effect:** blockers trail moving eyes or headlights.
**Current software guard:** capture, detection, GUI delivery, geometry, preview, and
stereo-skew timestamps are recorded and can be analysed.
**Next action:** complete the software timing matrix and external optical
photon-to-display measurement; introduce prediction only if the measured error budget
requires it.

### 11.8 Physical LCD limitations

An ordinary monitor is opaque. A stripped LCD panel may transmit some light but can
have poor transparency, viewing-angle dependence, polarization effects, low contrast,
and slow response. The software now has a disabled-by-default white-safe renderer, but
the electrical, optical, thermal, mapping, and power/signal failure behavior must be
evaluated independently from the camera geometry.

### 11.9 Coordinate handedness and mirrored driver processing

The current driver worker flips the frame horizontally before landmark geometry is
calculated. This produces a natural mirror preview, but it can also invert physical X
unless the mapping and extrinsic convention compensate for it. Before physical claims,
process geometry from an unmirrored frame or explicitly prove the handedness correction
with asymmetric left/right targets. Mirroring should be treated as a display choice,
not an undocumented coordinate transform.

---

## 12. Accuracy validation methodology

### 12.1 Why a fixed artificial driver target is required

A human cannot remain perfectly still, so live testing cannot distinguish natural head
motion from measurement noise. Build a rigid target with two high-contrast eye markers
separated by a measured distance, for example the selected test IPD. Mount it so its
distance, height, lateral position, and roll can be changed deliberately.

Use the artificial target first. Repeat a smaller set of tests with human participants
only after the measurement system is characterized.

### 12.2 Physical ground-truth intersection method

For a low-cost laboratory method:

1. mark measured left-eye and right-eye locations behind the panel plane;
2. place one or two LED sources at measured locations in front;
3. stretch a thin string from each light position to each eye position;
4. mark where each string crosses a paper grid fixed to the LCD plane;
5. record those physical X/Z positions as ground truth;
6. run the software without changing the structure; and
7. compare the predicted positions with the physical marks.

The string method is simple, visible, and appropriate for a low-budget proof of
concept. A laser alignment tool or surveyed jig can be used if available, but the
method and measurement uncertainty must be documented.

### 12.3 Error metrics

For predicted point `(Xp, Zp)` and measured point `(Xg, Zg)`:

```text
horizontal error = Xp - Xg
vertical error   = Zp - Zg
2D position error = sqrt((Xp - Xg)^2 + (Zp - Zg)^2)
```

Report at least:

- mean absolute error;
- root mean square error;
- median error;
- maximum error;
- 95th percentile error;
- stationary standard deviation or peak-to-peak jitter;
- percentage of valid frames;
- detection-loss duration;
- end-to-end latency; and
- percentage of trials in which the blocker fully covered the target ray.

### 12.4 Suggested independent variables

Driver-side tests:

- three depths: near, center, and far seating positions;
- three lateral positions: left, center, and right;
- three heights: low, center, and high;
- head roll angles such as `-15`, `0`, and `+15` degrees;
- yaw angles such as `-20`, `0`, and `+20` degrees;
- even light, dim light, and backlight;
- with and without glasses, if human testing is approved.

Road-side tests:

- multiple measured distances within the intended demonstration range;
- left, center, and right source positions;
- low and high source positions;
- one source and two sources;
- several brightness levels;
- static and slowly moving sources; and
- reflective distractors present and absent.

### 12.5 Comparing one-camera and two-camera driver setups

If a second driver camera becomes available, use the same rigid targets and trials for
both configurations. Compare:

- eye-coordinate error;
- depth error;
- stationary jitter;
- intersection error;
- valid-frame percentage;
- latency;
- calibration time; and
- total hardware cost.

The second camera is justified if the accuracy improvement is meaningful relative to
the thesis target and blocker-size requirements. A technically more complex solution
that provides no meaningful final-intersection improvement should not be selected only
because it uses stereo.

### 12.6 Minimum repeatability practice

- Record all camera indices, resolutions, exposure settings, and thresholds.
- Record exact frame dimensions and baselines.
- Save the calibration file identifier used for each trial.
- Repeat each condition several times, ideally on different setup sessions.
- Do not tune acceptance limits after seeing the results.
- Preserve both successful and failed samples.
- Photograph the apparatus and every ground-truth layout.

---

## 13. Recommended implementation stages

### Stage 0 - Original visualization concept

**Goal:** prove the ray-plane idea visually.
**State:** completed.

Outputs included a virtual windshield, driver point, light point, rays, intersection
markers, controls, and movement simulation.

### Stage 1 - Operator interface and session control

**Goal:** make testing predictable and prevent source confusion.
**State:** completed.

Completed work includes:

- Run, Standby, and Stop;
- four operating modes;
- source-dependent control locking;
- separate camera cards;
- resizable workspace and left-aligned camera strip;
- telemetry separated from camera content; and
- modern 3D and theme controls.

### Stage 2 - Affordable single-camera demonstration paths

**Goal:** support one driver camera and one road camera before full stereo hardware.
**State:** functionally implemented; accuracy partial.

Completed work includes MediaPipe eye tracking, one-point driver calibration,
bright-light detection, same-lamp road range estimation, exposure warnings, and camera
throughput improvements.

### Stage 3 - Independent binocular eye geometry

**Goal:** preserve head roll and calculate a path for each physical eye.
**State:** implemented in the current working source and live-tested.

Completed work includes separate eye signals, two-eye state, per-eye rays, labeled
intersections, two-eye 3D markers, and an automated head-roll regression.

### Stage 4 - Stabilization and research logging

**Goal:** turn live observations into repeatable measurements.
**State:** logging, timing, stale-data guards, and analysis support are implemented;
driver-eye filtering and the physical dual-camera soak remain open.

Completed software work includes:

- timestamped telemetry and per-stream video with frame sidecars;
- session metadata, recording errors, and drop counters;
- capture, detection, GUI-delivery, geometry, preview, and stereo-skew timing;
- confidence/state records and 250 ms stale-sample rejection;
- safe recording shutdown; and
- automated diagnostics, latency, and recovery tests.

Remaining work is to complete the ten-minute dual-camera soak, add and validate a
binocular-preserving driver-eye filter, and report raw versus filtered measurements.

### Stage 5 - Complete calibration chain

**Goal:** express all positions in verified LCD-relative centimetres.
**State:** the road-pair operator workflow and guarded intrinsic/stereo backends exist;
installed physical/filter validation, ChArUco/held-out metrics, extrinsic integration,
and complete live-profile application remain missing.

Tasks:

1. replace or augment the initial checkerboard stages with ChArUco and held-out metrics;
2. implement post-filter geometric and photometric verification;
3. collect fit and held-out windshield targets for each installed camera;
4. pass the predeclared centimetre limits and repeatability/remount checks;
5. apply only device-, resolution-, intrinsic-, and mount-compatible profiles in the
   live pipelines; and
6. validate known 3D targets after integration.

### Stage 6 - Physical road stereo and multiple headlights

**Goal:** triangulate one and then two independent simulated headlights.
**State:** multi-object detection, stable identities, and stereo candidate matching are
implemented in software; physical stereo and multi-lamp validation remain.

Tasks:

1. mount the cheap road cameras rigidly;
2. calibrate and measure their baseline;
3. validate one static torch over several distances;
4. tune threshold, exposure, area, blur, and cleanup settings using the new processing
   previews;
5. validate rectified-row matching for two physical sources;
6. measure stable-ID behavior during source crossing and dropout; and
7. validate two-torch intersection results.

### Stage 7 - Physical LCD blocking

**Goal:** replace visualization-only points with real display output.
**State:** experimental software output implemented; physical bench validation pending.

Implemented software work includes a secondary-display requirement, disabled-by-default
activation, full-screen white safe state, feathered black spots, exact pixel-boundary
handling, and clearing on lost/stale/Stop/shutdown states.

Remaining tasks:

1. characterize the stripped panel's transparent/dark states and polarization;
2. map LCD pixels to independently measured windshield coordinates;
3. derive blocker radius and any merge policy from the error budget;
4. measure optical coverage, obscured area, response, ghosting, and temperature;
5. verify signal/power failure reaches the transparent state; and
6. perform the dynamic, binocular, multi-light, and string/grid experiments.

### Stage 8 - Optional driver stereo

**Goal:** improve driver depth only if single-camera validation is insufficient.
**State:** planned optional upgrade.

Tasks:

1. install the reserved second driver camera;
2. perform driver-pair intrinsic and stereo calibration;
3. capture near-synchronized frames;
4. locate both pupils in both images;
5. match left pupil to left pupil and right to right;
6. triangulate each eye independently;
7. transform the eyes into LCD coordinates; and
8. compare against the single-camera baseline using the same test matrix.

### Stage 9 - Final evaluation and packaging

**Goal:** produce defensible thesis results and a repeatable demonstration.
**State:** future.

Tasks:

- freeze hardware and software versions;
- execute the full validation matrix;
- analyze accuracy, jitter, latency, availability, blocker coverage, and cost;
- document failure cases and limitations;
- rebuild and launch-test the standalone executable;
- prepare demonstration instructions; and
- archive source, calibration files, raw logs, analysis scripts, photos, and results.

---

## 14. Affordable hardware strategy

### 14.1 Recommended purchase order

1. Use the existing laptop/integrated camera for initial driver tracking.
2. Purchase two inexpensive, preferably identical USB webcams for road stereo.
3. Build the rigid frame and calibration targets.
4. Use ordinary LED torches as controlled headlights.
5. Validate the road pair and the single driver camera.
6. Reserve remaining funds for the physical LCD/controller and mounting materials.
7. Purchase a second driver camera only if the measured single-camera driver error
   threatens the required blocker coverage.

### 14.2 Selection criteria for cheap webcams

Prioritize practical testability over advertised megapixels:

- stable 640x480 or 720p output at a real 30 FPS;
- MJPEG support to reduce USB bandwidth;
- manual focus or a focus setting that can be locked;
- manual exposure control if accessible;
- similar field of view between units;
- ability to open multiple cameras simultaneously;
- standard tripod or removable-case mounting; and
- local availability for an identical replacement.

### 14.3 Risks of removing webcam housings

Opening cheap webcams may help produce a compact rigid pair, but it can damage the
sensor cable, disturb lens focus, expose the board to static electricity, or remove
structural support. If housings are removed:

- label left/right devices permanently;
- avoid rotating the lens barrel after calibration;
- mount the circuit boards without bending;
- protect exposed electronics;
- provide cable strain relief; and
- recalibrate after any mechanical change.

---

## 15. Operating procedure for a controlled demonstration

### 15.1 Before starting

1. Confirm that every camera is rigid and unchanged since calibration.
2. Confirm the LCD plane dimensions and origin marks.
3. Close other applications that may use the webcams.
4. Connect cameras consistently so their indices remain known.
5. Remove reflective objects from the road-camera view.
6. Use stable, diffuse lighting on the driver's face.
7. Place the torches at measured positions.
8. Load only calibration profiles matching the current devices and settings.

### 15.2 Isolated driver test

1. Select **Headlight Position Fixed**.
2. enter a measured fixed light position;
3. select the driver camera;
4. use Standby to position the driver;
5. switch to Run;
6. test left/right, up/down, closer/farther, yaw, and head roll; and
7. record raw depth stability and intersection movement.

### 15.3 Isolated road test

1. Select **Driver Position Fixed**.
2. enter a measured fixed driver position;
3. select single or stereo road setup;
4. use Standby to aim the cameras and torches;
5. switch to Run;
6. test known source locations; and
7. record detection, range, and intersection error.

### 15.4 End-to-end test

1. Select **Fully Auto**.
2. verify that camera indices do not conflict;
3. confirm both required previews in Standby;
4. switch to Run;
5. move the driver and lights independently at controlled speeds;
6. observe each eye/light intersection;
7. record data and video; and
8. switch to Stop before moving hardware.

---

## 16. Safety, ethics, and research boundaries

- Do not test the prototype while driving or on an active public road.
- Do not shine unsafe high-intensity lights directly into participants' eyes.
- Use the lowest brightness that reproduces the camera and LCD behavior being studied.
- Obtain informed consent before recording identifiable faces.
- Store face video and calibration data securely and define a retention period.
- Report participant count and selection honestly; do not generalize one person's IPD
  calibration to all drivers.
- Treat loss of eye or light tracking as an invalid state, not as a valid last-known
  blocker position.
- Do not describe the prototype as preventing accidents or guaranteeing driver safety.
- Clearly distinguish the indoor demonstrator from automotive certification.

---

## 17. Evidence to collect for the later thesis

The following evidence should be collected continuously as the project develops. It
can later support the final project archive and thesis:

- a dimensioned drawing of the wooden structure;
- photographs of camera and LCD mounting;
- camera models, serial/device identifiers, and purchase costs;
- camera resolutions, codecs, frame rates, focus, and exposure settings;
- final optical-filter material, tint, orientation, spacing, mount, and calibration
  state if attenuation is used;
- saved detector settings/profile identifiers and camera-control readback;
- printed checkerboard dimensions;
- intrinsic, stereo, and extrinsic calibration files;
- calibration reprojection errors;
- source commit identifier and dependency versions;
- raw CSV logs with timestamps;
- representative synchronized videos;
- the ground-truth position table;
- scripts or spreadsheets used to compute metrics;
- plots of measured versus estimated depth;
- plots of stationary jitter and step response;
- intersection-error distributions;
- end-to-end latency results;
- one-camera versus two-camera comparisons if driver stereo is tested;
- LCD blocker coverage and obscured-area results;
- failure examples; and
- a bill of materials and final cost comparison.

---

## 18. Possible future thesis structure

This outline is a planning aid only. It should be revised later to match the completed
system, the university requirements, and the results that are actually measured.

### Chapter 1 - Introduction

Describe night-time glare, the motivation for localized rather than full-field
attenuation, the low-cost research objective, research questions, contributions, and
scope.

### Chapter 2 - Background and related work

Review driver glare, active visors, transparent/stripped LCD behavior, eye tracking,
camera calibration, stereo vision, bright-source detection, ray-plane geometry,
real-time latency, and prior active glare-control systems. Formal references must be
collected and verified separately.

### Chapter 3 - Requirements and system design

Present the laboratory scenario, functional/non-functional requirements, affordable
hardware decision, coordinate frame, four operating modes, session states, architecture,
and safety constraints.

### Chapter 4 - Implementation

Explain the Qt application, camera workers, MediaPipe landmarks, single-camera depth,
road-light detector, stereo triangulation, calibration profiles, per-eye/per-light
geometry, visualization, and planned/implemented LCD renderer.

### Chapter 5 - Experimental methodology

Document the frame, fixed artificial eyes, torch positions, string/grid ground truth,
calibration sequence, test variables, repetitions, metrics, and single-versus-stereo
comparison.

### Chapter 6 - Results

Report accuracy, jitter, tracking availability, frame rate, latency, blocker coverage,
blocked screen area, failure cases, and cost. Do not mix simulated results with physical
measurements without labels.

### Chapter 7 - Discussion

Interpret which errors dominate, whether low-cost hardware is sufficient for the
controlled demonstration, when driver stereo is justified, how calibration affects the
result, and what prevents road deployment.

### Chapter 8 - Conclusion and future work

Answer the research questions directly. Summarize contributions and propose hardware
synchronization, improved sensors, predictive filtering, robust multi-headlight
association, optical improvements, and automotive-grade validation as future work.

---

## 19. Recommended figures and tables

Suggested figures:

1. complete physical system concept;
2. coordinate axes and LCD plane;
3. two eyes by two lights producing four rays;
4. current software data flow;
5. bright-source intermediate masks, candidate confidence, and stable IDs;
6. final optical-filter mount and before/after detector images;
7. driver monocular depth principle;
8. road stereo disparity principle;
9. camera/windshield/LCD calibration hierarchy;
10. wooden frame with measured dimensions;
11. artificial-eye and string ground-truth setup;
12. screenshots of the four operating modes and dark/gray scene themes;
13. raw versus filtered driver depth;
14. predicted versus measured intersection locations; and
15. error distribution and capture-to-display latency timeline.

Suggested tables:

1. functional requirements and completion state;
2. hardware bill of materials;
3. calibration results;
4. camera performance;
5. driver accuracy by pose;
6. road-light accuracy by distance;
7. final intersection error;
8. one-camera versus two-camera driver comparison;
9. blocker coverage versus blocked area; and
10. current limitations and future solutions.

---

## 20. Current next development actions

The project team should continue with the following actions in order:

1. Use `docs/plans/VALIDATION_PLAN.md` as the active work queue and retain the current
   98-test software baseline.
2. Rigidly mount the now-available road pair with final filters; capture and fit the
   chessboard, check baseline and independent stationary-light distances, then tune
   stereo in Driver Position Fixed mode. Reintroduce the driver camera and complete
   the Stage 2 recording soak, inspecting timestamps, videos, drops and shutdown.
3. Freeze the camera/filter mounts and collect the Stage 3 driver and road-light
   ground-truth matrices with predeclared limits and repeated positions.
4. Complete Stage 4 physical camera-to-windshield fitting, held-out validation,
   remount repeatability, and live compatible-profile integration.
5. Execute the Stage 5 physical eye-to-light intersection matrix.
6. Complete Stage 6 software timing, external photon-to-display latency, and failure
   recovery tests.
7. Characterize and validate the Stage 7 stripped LCD, mapping, blocker radius,
   dynamic behavior, and transparent fail-safe state.
8. Run Stage 8 illumination, weather-like, thermal, vibration, endurance, and gated
   stationary/closed-course tests only after the earlier gates pass.
9. Add driver-eye filtering and prediction only from measured jitter/latency needs,
   preserving the eye separation vector and reporting added delay.
10. Decide whether optional driver stereo is justified by measured single-camera
    error, blocker coverage, complexity, and remaining budget; then rebuild/package
    the current source after the next stable milestone.

---

## 21. Glossary

| Term | Meaning in this project |
|---|---|
| IPD | Interpupillary distance: physical distance between the two eyes |
| Intrinsics | Camera focal length, principal point, and lens distortion parameters |
| Extrinsics | Rotation and translation between a camera coordinate frame and another frame |
| Baseline | Distance between the optical centers of a stereo camera pair |
| Disparity | Difference in the matched point's horizontal image location between stereo views |
| Triangulation | Recovering a 3D point from its observations in two calibrated cameras |
| Rectification | Warping stereo images so corresponding points lie on approximately the same row |
| Ray-plane intersection | Point where the straight eye-to-light line crosses the LCD plane |
| Jitter | Frame-to-frame coordinate variation while the physical target is stationary |
| Latency | Delay between a physical event and the corresponding displayed blocker update |
| Dropout | Temporary absence of a valid eye or light observation |
| Ground truth | Independently measured physical position used to evaluate the estimate |
| Fail-safe clearing | Removing blockers when tracking data is invalid or too old |

---

## 22. Source-of-truth documents

Use the following files together:

- `docs/README.md` - documentation index and source-of-truth order;
- `README.md` - quick project introduction and launch instructions;
- `PROJECT_STATUS.md` - requirement-by-requirement implementation matrix;
- `docs/plans/VALIDATION_PLAN.md` - current ordered validation status;
- `docs/guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md` - detailed operational and physical
  test workflow;
- `docs/plans/FUNCTIONAL_TEST_PLAN.md` - concise pass/fail functional checks;
- `docs/archive/UI_CAMERA_MODE_IMPLEMENTATION_CHECKLIST.md` - completed UI/mode
  redesign history; and
- this report - consolidated design rationale, verified milestone history through
  2026-10-14, staged roadmap, and later-thesis reference.

When documents disagree, inspect the current source and tests, then update the
documentation. Do not assume that a built executable contains the latest source
changes.

---

## 23. Current project position and continuation

The project has successfully progressed from a single-point visualization into a
structured research application with explicit operating modes, controlled session
states, independent eye geometry, camera previews, multi-source road-light detection,
stereo foundations, timestamped research recording, guarded extrinsic-calibration
tools, timing/stale-data instrumentation, an experimental fail-safe LCD renderer, and
a testable ray-intersection model. Road-pair chessboard calibration is now exposed
in the UI; a strict timestamped-recording soak verifier is also available; 98
automated tests pass on Python 3.13.

The most important scientific work remains physical: completing the dual-camera soak,
establishing and applying a shared measured coordinate system, quantifying eye/light
and intersection error, measuring external latency and recovery, validating multiple
physical lights, and proving the stripped LCD's mapping, attenuation, thermal, and
safe-state behavior. The earlier scan finding only camera index 0 is historical:
the operator now reports two road cameras plus the driver camera. The immediate
prerequisite is physical road-pair calibration and tuning, then the recording soak.

This is the current milestone, not the end of the project. This report should be revised
after major software changes, hardware construction, calibration experiments, physical
LCD work, and accuracy testing so that it continues to represent the real state of the
research.

The low-cost concept remains feasible as a controlled laboratory demonstrator. Cheap
webcams and a rigid wooden frame can provide a meaningful proof of concept if the team
treats calibration, repeatability, error measurement, and limitations as central
research results rather than assuming that visually plausible tracking is accurate.

---

## Appendix A. Consolidated multi-chat record

On 2026-10-14, eight separate chat summaries were compared against the current source,
tests, documentation, artifacts, and Git history. Their durable contributions are
incorporated into this reference as follows:

| Summary | Consolidated contribution | Disposition |
|---|---|---|
| `SUM-01` | Multi-source detector, processing previews, saturated-core handling, camera-role selection, detector benchmark, and sunglass-filter observation | Retained with physical-validation cautions |
| `SUM-02` | Run/Standby/Stop, four operating modes, affordable stereo strategy, binocular geometry, driver-depth filtering rationale, and ground-truth method | Retained; older test counts superseded |
| `SUM-03` | Camera-maturity classification, risk register, configuration-locking rules, and implementation-versus-validation distinction | Retained in status and challenge sections |
| `SUM-04` / `GT-CHAT-20261014-04` | Python/MediaPipe compatibility, bundled model, live camera checkpoints, MJPEG/backend improvements, guided demonstration calibration, and Git handoff | Retained; machine-specific indexes are not requirements |
| `SUM-05` / `GT-CHAT-20261014-05` | Dark/gray scene preference, layered grid, responsive UI, telemetry readability, and verified calculation-guide PDF | Retained as usability and educational evidence |
| `SUM-06` / `GT-CHAT-20261014-06` | Dashboard architecture, icon/ribbon evolution, rejected themes, coordinate-pipeline audit, mirror-handedness risk, and commit chronology | Retained; historical findings checked against current source |
| `SUM-07` / `GT-CHAT-20261014-07` | Repository maturity boundary and evidence-based documentation authority rules | Retained; midpoint-only findings superseded by current binocular integration |
| `SUM-08` / `GT-CHAT-20261014-08` | Unverified React Three Fiber/Vite visualization experiment outside the active repository | Recorded as unintegrated exploration, not a current feature |

Conflicts were resolved using current source and automated tests first, followed by
`PROJECT_STATUS.md`, maintained documentation, Git history, dated physical evidence,
and finally the chat summaries. Historical 4-, 11-, 12-, and 27-test checkpoints remain
development provenance; the authoritative current software result is 107 passing tests.
