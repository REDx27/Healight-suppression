# Stereo Camera Bring-Up and UI Simplification Plan

> Created: 2026-11-03  
> Status: implementation started; first guided chessboard slice complete
> Applies to: two road-facing USB cameras plus the existing driver camera  
> Safety: stationary laboratory prototype only; no public-road or moving-vehicle use

## 1. Outcome

Build a guided, fail-closed road-stereo workflow that:

1. detects the selected road-camera pair after startup;
2. offers **Calibrate now** and **Skip for now** without silently opening cameras;
3. calibrates each road camera individually before fitting their stereo relationship;
4. measures, rather than assumes, whether the two cameras provide compatible image
   resolution, sharpness and brightness response;
5. verifies the rig again after the external sunglass lenses are installed;
6. tracks sparse bright light sources without requiring a textured surface;
7. produces no metric stereo position when correspondence or calibration is invalid;
8. reduces the main interface to the controls needed for this physical workflow; and
9. preserves raw calibration and validation evidence for the research record.

### Implementation checkpoint - 2026-11-03

The first runnable slice is implemented:

- camera discovery offers **Calibrate now** or **Skip for now** once per launch when
  the selected ordered road pair lacks a compatible profile;
- Skip leaves metric stereo fail-closed while preserving previews and other modes;
- the dialog enforces LEFT intrinsics, RIGHT intrinsics, then paired stereo geometry
  using the two fixed individual results;
- every stage rejects near-duplicate poses and archives raw images and reports;
- the stereo fit gates RMS, rectified row error, baseline sign and finite matrices
  before an active ordered profile can be saved; and
- the Python 3.13 regression suite contains 110 passing tests, including automatic
  two-light association in rough and calibrated stereo paths.

Live diagnosis on 2026-11-03 found the immediate bring-up failure: indices 0 and 2
are the external road pair, while index 1 is the integrated driver camera; the old
default role assignment was wrong. The road pair could not retrieve simultaneous
640 x 480 frames on the shared USB root hub. Both road streams were stable at
320 x 240/15 FPS, and the three-stream mix remained stable when the driver camera
stayed at 640 x 480/30 FPS. The implementation now uses those measured profiles,
verifies real frames during discovery, falls back from dead backend handles, and
rejects frame-edge/elongated ceiling-light candidates.

For pre-calibration setup only, missing/incompatible stereo profiles now permit a
clearly labelled **ROUGH UNCALIBRATED** single-source match. It uses relaxed image-row
pairing and an assumed depth solely to confirm that the same isolated light is visible
in both feeds. Rough sources may render amber, explicitly approximate demo
intersections, but remain outside metric validity, research measurements and physical
LCD output. Saturated vertical color-bar/test-pattern frames are marked invalid per
stream rather than reported as an online camera.

This checkpoint deliberately retains the proven checkerboard detector. ChArUco,
held-out/per-view metrics, post-filter verification, photometric measurement and UI
reduction remain the next slices; no physical calibration has been marked complete.

The goal is not to make dissimilar camera internals physically identical. Software can
rectify their geometry, select a common capture mode, compensate some brightness
differences and reject an unsuitable pair. It cannot recreate missing detail, repair
poor focus, eliminate motion skew, or hardware-synchronize ordinary USB webcams.

## 2. Research conclusions that determine the design

### 2.1 Geometry, appearance and time are different calibration problems

- **Intrinsic calibration** measures each camera's focal lengths, principal point and
  lens distortion. Each physical camera receives its own profile; identical housings
  do not justify shared values.
- **Stereo calibration** measures rotation and translation between the already-fixed
  pair, then rectifies both views so matching points lie on the same image row.
- **Photometric matching** measures exposure, nonlinear response, black level and
  vignetting differences. It improves comparable blob detection but does not change
  camera geometry.
- **Synchronization** concerns exposure time. Calling `grab()` on both cameras before
  `retrieve()` makes frames closer in time, but OpenCV explicitly describes this as a
  technique for cameras *without* hardware synchronization. It is not a common clock
  or simultaneous exposure guarantee.

The application must report these as separate results. A successful intrinsic or
stereo fit must never be labelled “cameras synchronized.”

### 2.2 Use ChArUco for the new individual workflow

The current chessboard workflow remains a useful fallback. The new wizard should use
a printed, measured, matte ChArUco board by default because its chessboard-derived
corners retain sub-pixel accuracy while marker IDs allow partial views. OpenCV calls
ChArUco preferable to ordinary ArUco when calibration precision matters.

Use `calibrateCameraExtended` so each camera report includes overall RMS, per-view
errors and parameter uncertainty. Reject poor views transparently; preserve them in
the session archive rather than deleting evidence.

### 2.3 A bright point does not require dense surface texture

Texture is needed when dense stereo must discover a correspondence for most image
pixels. GlareTracker needs sparse stereo: detect a headlight centroid independently in
each image, establish that the two centroids represent the same physical source, and
triangulate those corresponding points. OpenCV's `triangulatePoints` accepts explicit
corresponding 2D points; it does not require a textured surface.

The dark lenses can help candidate isolation, but they do not solve correspondence.
The system must still use epipolar position, disparity, blob properties, temporal
motion and ambiguity rejection. Point/laser measurement literature also follows the
sequence: spot detection, correspondence, then triangulation.

### 2.4 Filters require a second gate

The requested initial geometry calibration will occur before the external sunglass
lenses are applied so the target is easy to see. After each lens is fixed in its final
holder, the bare-camera result becomes provisional:

- the filter changes transmission and potentially focus/sharpness;
- curved, wedged, non-flat or tilted material can refract rays and change the effective
  camera model;
- the two filters may have unequal tint, attenuation or vignetting; and
- automatic exposure can make two filtered views fluctuate differently.

Therefore, final activation requires a bright-board geometric verification through
the installed filters and a separate photometric matching step. If validation exceeds
the declared geometric limit, the full individual and stereo calibration must be
repeated through the filters using a brighter/backlit target. Never “correct” a failed
geometric test using only brightness normalization.

## 3. User-facing workflow

### 3.1 Startup readiness prompt

Run camera discovery after the main window appears. Do not take camera ownership until
the operator responds. Once discovery completes:

1. identify the currently selected road-left and road-right indices;
2. require two distinct devices and show live identity confirmation thumbnails;
3. check for a compatible, accepted profile using camera order, negotiated resolution,
   capture mode, profile version and filter state;
4. show one prompt only when the pair is missing, incompatible, provisional, or due
   for post-filter verification.

Prompt actions:

- **Calibrate now** — stop all tracking/recording, claim only the two road cameras and
  launch the wizard;
- **Skip for now** — dismiss for the current application session. Manual and
  single-camera tools remain available; stereo may show previews but metric stereo
  positions, intersections and LCD output remain disabled.

Do not prompt when fewer than two road cameras are assigned. Do not calibrate every
plugged webcam indiscriminately: the user must confirm which physical camera is LEFT,
which is RIGHT, and which is the separate driver camera. If more than two candidates
exist, require pair selection.

### 3.2 Wizard page sequence

#### Page 1 — Identify and prepare

- show index, backend, negotiated width/height/FPS and a thumbnail for each camera;
- operator confirms LEFT and RIGHT as viewed from behind the rig toward the scene;
- require a rigid mount, measured optical-centre baseline and permanent labels;
- require both feeds to use one common resolution, FPS request and pixel format;
- confirm **no external sunglass lenses installed** for the initial pass;
- warm cameras for five minutes before photometric measurements.

#### Page 2 — Capture-mode and image-quality check

- request the same resolution/FPS/MJPEG mode on both devices and read back actual
  values;
- display sharpness, clipping percentage, mean/percentile brightness and noise proxy;
- attempt to lock focus, exposure, gain and white balance only where the backend
  reports support;
- record requested and read-back properties independently for each camera;
- fail if resolution differs, either feed is unreadable, gross blur is present, or the
  common usable overlap is insufficient. Warn rather than pretend unsupported camera
  controls were accepted.

This page determines compatibility; it does not manufacture equal sensor detail.

#### Page 3 — LEFT camera intrinsics

- show the measured ChArUco board specification and printing instructions;
- capture at least 20 accepted views spanning centre, edges, corners, near/far and
  strong tilts;
- show a frame-coverage heatmap and pose-diversity indicator;
- prevent near-duplicate captures and flag blur, clipping and too-small patterns;
- reserve several views as held-out validation rather than fitting every image;
- fit with `calibrateCameraExtended`, show per-view error and uncertainty, and allow a
  new capture set if declared limits fail.

#### Page 4 — RIGHT camera intrinsics

Repeat Page 3 independently. Never copy the LEFT camera matrix or distortion values.
Use the same physical board measurement and negotiated image size.

#### Page 5 — Stereo relationship

- cameras and mount must remain fixed after the individual fits;
- capture at least 20 paired, stationary board poses visible in both cameras;
- use the accepted individual intrinsics with `CALIB_FIX_INTRINSIC`;
- estimate `R`, `T`, `E`, `F`, rectification transforms and projection matrices;
- verify baseline magnitude against the ruler measurement;
- calculate held-out rectified vertical error, left/right reprojection error and valid
  common field of view;
- reject reversed order, non-horizontal/implausible baseline, excessive error, or
  insufficient pose diversity.

#### Page 6 — Initial result

- display PASS/FAIL per camera and for the pair;
- save an immutable candidate archive containing raw frames and reports;
- activate only a complete passing set;
- mark it `bare_filters` and **provisional until post-filter verification**;
- instruct the operator to close the wizard, rigidly attach and label the sunglass
  lenses, then start the filter-verification stage.

#### Page 7 — Post-filter verification and photometric matching

- record a stable ID for each physical filter and the side on which it is installed;
- use a brightly illuminated/backlit board through the final filters;
- test held-out corner reprojection and rectified row error using the bare profile;
- if geometry fails, require full recalibration through the installed filters;
- capture dark frames, a uniform matte field and several known brightness levels;
- measure each camera's black level, clipping, response, vignetting and sharpness;
- choose stable per-camera exposure/gain settings where supported;
- store conservative grayscale normalization/flat-field parameters for candidate
  scoring, not for changing geometric coordinates;
- capture a bright test point at several image positions and require it to remain
  detectable, unsmeared and not fully saturated in both views.

Only this page can change the pair state to `final_filters_verified`.

## 4. Profile and evidence design

One versioned pair profile should reference, rather than duplicate:

- left/right physical IDs and current camera indices;
- left/right intrinsic profiles and held-out reports;
- stereo `R/T/E/F/R1/R2/P1/P2/Q` and baseline;
- requested and read-back resolution, FPS, codec, focus/exposure/gain/white balance;
- bare/filter state plus left/right filter IDs;
- photometric response and vignetting data;
- board type, dictionary, dimensions and measured units;
- declared limits, software version, UTC timestamps and source commit;
- raw-session directories and checksums; and
- invalidation reasons after a camera, filter, focus, resolution or mount change.

Profiles must be written atomically. A failed attempt writes a report but never
replaces the active profile. Keep the last accepted profile for rollback, while still
refusing to apply it to incompatible hardware.

## 5. Sparse bright-source stereo pipeline

### 5.1 Candidate extraction

For each raw camera frame independently:

1. subtract a captured static background when available;
2. calculate bright-source saliency in grayscale/intensity space;
3. segment plausible bright cores at multiple thresholds;
4. reject excessive clipping, large reflections and edge-truncated blobs;
5. estimate a sub-pixel centre using intensity-weighted centroid or a robust local
   Gaussian/core fit; and
6. retain centre, area, diameter, peak/core intensity, confidence and timestamp.

Do not require the surrounding scene to have texture. Do not rely on absolute raw
brightness being equal across the two different camera internals.

### 5.2 Correspondence

Rectify candidate centres using the final pair profile. Form a pair only when all
hard gates pass:

- vertical/epipolar error within the calibrated tolerance;
- positive disparity and a disparity/range inside the measured operating envelope;
- timestamps inside the declared software-skew limit;
- compatible blob size and normalized intensity bands; and
- physically plausible position after triangulation and reprojection.

For the first milestone, support **one stationary light only**. This removes the main
identity ambiguity and gives a defensible accuracy baseline.

For multiple lights, construct a cost matrix from row error, temporal prediction,
disparity continuity, size ratio and normalized intensity. Use one-to-one assignment
and require a clear best-versus-second-best margin. If correspondence is ambiguous,
emit no 3D observation and clear the blocker; never guess.

A controlled laboratory LED may be temporally coded/blinked to test correspondence.
Real vehicle headlights are not under system control, so production correspondence
cannot depend on coded blinking.

### 5.3 Triangulation and uncertainty

- use the rectified projection matrices with `cv2.triangulatePoints`;
- convert homogeneous output safely and reject points behind either camera;
- reproject the 3D point into both images and reject excessive pixel residual;
- transform from the primary camera frame into the windshield frame only after a
  compatible installed extrinsic profile exists;
- report disparity, row error, reprojection error and estimated range uncertainty;
- reject very small disparity where depth uncertainty exceeds the declared limit.

The approximate sensitivity is proportional to `focal * baseline / disparity²`, so
far lights with tiny disparity need stricter uncertainty reporting, not false precision.

### 5.4 Time behavior

Start validation with a stationary light. Then move it slowly while logging primary
and secondary capture-completion skew. Generic USB capture remains unsuitable for a
moving-target accuracy claim until externally measured skew and resulting range error
meet predeclared limits. If they do not, the options are a hardware-synchronized pair,
hardware trigger support, or a measured prediction model—not a UI threshold change.

## 6. Interface simplification

### 6.1 Main workflow — keep visible

- Run / Standby / Stop and one overall readiness banner;
- workflow choice: **Stereo Setup**, **Stereo Light Test**, **Full System**;
- driver, road-left and road-right identity/thumbnail/status;
- **Calibrate / Verify Stereo** action and concise profile state;
- one detection preset selector plus a simple sensitivity adjustment;
- original/detection previews and left/right candidate/match counts;
- recording toggle, recording path and failure status; and
- calculated coordinates/intersections only when inputs are valid.

### 6.2 Move out of the main workflow

Place these in a collapsed **Advanced Diagnostics** page, hidden by default:

- exposure, brightness, contrast and gain requests/readback;
- adaptive threshold, raw brightness ceiling and saliency floor;
- source confidence, min/max area, blur and morphology passes;
- background-difference threshold and ID match distance;
- legacy single-camera assumed depth and HFOV;
- manual driver/light coordinates and movement simulation; and
- calibration fit details and per-view metrics.

Place ground-truth coordinates, condition IDs and analyzers in a dedicated
**Research Validation** page. Place windshield/LCD dimensions and output controls in
an **Installation / Hardware Validation** page, still disabled by default.

### 6.3 Remove rather than merely hide

- remove **Vehicle Type** and its generated 1/2/4-light offsets. Camera detection is
  deliberately source-based, and physical lights should be observed independently;
- remove the **Daylight Phone-Light Preset** from the normal product flow. Retain a
  versioned legacy preset only in test fixtures if comparison evidence requires it;
- remove manual camera XYZ from the normal workflow after live, compatible
  camera-to-windshield extrinsics replace the visualization-only value; and
- remove duplicate calibration entry points once the startup wizard covers the same
  task. Keep only one authoritative profile/status path.

Do not delete research recording, fail-safe clearing, raw evidence, or diagnostic
values needed for reproducibility. Simplification means fewer operator decisions,
not loss of scientific evidence.

## 7. Implementation order and gates

### Phase A — state model and startup prompt

- add versioned calibration registry and explicit pair/filter states;
- prompt only after discovery and only for an unready selected pair;
- implement Calibrate now / Skip for now and camera-ownership guards;
- test no-camera, one-camera, two-camera, extra-camera, valid-profile and stale-profile
  paths without physical hardware.

Exit: no automatic camera conflict; Skip never enables metric stereo; a valid final
profile avoids repeated prompts.

### Phase B — individual ChArUco calibration

- verify `cv2.aruco` in development, packaged builds and declared dependencies;
  retain the current chessboard path when the module is unavailable rather than
  starting a partially supported ChArUco session;
- board generator/print specification and measured metadata;
- independent raw capture, coverage/pose checks and held-out views;
- extended calibration metrics and guarded profile writes;
- synthetic and fixture-image regression tests.

Exit: both cameras have independent passing profiles at the negotiated mode.

### Phase C — stereo calibration and rectification

- paired capture using fixed intrinsics;
- baseline, rectification and held-out gates;
- profile activation/rollback and full evidence archive;
- compare the new result with the existing chessboard path before retiring it.

Exit: ruler-consistent baseline and declared held-out error, still marked provisional.

### Phase D — filters and photometric verification

- filter identity/state, bright-board geometry check and invalidation;
- capture/readback matching, flat-field/response measurements and quality report;
- filtered bright-point detection across the common view.

Exit: final-filter geometry and visibility pass; profile state is
`final_filters_verified`.

### Phase E — sparse light matching

- robust centroid, rectified gates and triangulation/reprojection;
- single stationary light, then slow motion, then multiple-light ambiguity rejection;
- ground-truth depth/lateral matrix with repeated runs and uncertainty.

Exit: measured held-out ranges pass limits declared before inspecting results.

### Phase F — interface reduction

- introduce the three task-focused pages;
- move advanced/research/hardware controls;
- delete vehicle-type generation and obsolete normal-flow preset/duplicates;
- add UI visibility and workflow regression tests.

Exit: a new operator can reach calibration and a one-light stereo test without
adjusting algorithm internals; advanced evidence remains accessible.

### Phase G — resume ordered validation

1. complete the ten-minute road-stereo recording soak;
2. reintroduce the driver camera and repeat with all three streams;
3. perform Stage 3 ground truth;
4. integrate and physically validate camera-to-windshield extrinsics;
5. continue physical intersection, latency/recovery, LCD and environmental stages.

## 8. Required physical acceptance evidence

Before calling road stereo functional, retain:

- labelled rig/filter photographs and measured baseline;
- board print measurement and flatness record;
- independent left/right intrinsic raw sets and reports;
- paired stereo raw set, fit and held-out report;
- bare-versus-filter geometric comparison;
- photometric/sharpness/readback report for both filtered cameras;
- at least three repeats at each known light position;
- depth/lateral error, RMSE, p95, max, jitter, detection rate and dropout duration;
- capture skew and motion-condition evidence; and
- source commit, profile checksums and complete diagnostic session.

Automated tests prove the workflow and mathematics only. They cannot mark any of these
physical gates complete.

## 9. Primary technical references

- [OpenCV camera calibration and 3D reconstruction](https://docs.opencv.org/4.11.0/d9/d0c/group__calib3d.html)
  — individual calibration, stereo calibration, rectification and triangulation APIs.
- [OpenCV camera-calibration guidance](https://docs.opencv.org/5.0/main_modules/calib.html)
  — varied poses/distances, extended per-view errors and stable fitting guidance.
- [OpenCV ChArUco detection](https://docs.opencv.org/4.12.0/df/d4a/tutorial_charuco_detection.html)
  — accurate chessboard-derived corners with partial-view marker identification.
- [OpenCV calibration-pattern guidance](https://docs.opencv.org/5.0/tutorials/calib3d/camera_calibration_pattern/camera_calibration_pattern.html)
  — flat matte targets, borders, feature count and element size.
- [OpenCV VideoCapture reference](https://docs.opencv.org/4.10.0/d8/dfe/classcv_1_1VideoCapture.html)
  — multi-camera `grab`/`retrieve` behavior and backend-dependent property support.
- [Kim and Pollefeys, robust radiometric calibration and vignetting correction](https://pubmed.ncbi.nlm.nih.gov/18276964/)
  — nonlinear response, exposure and vignetting as separate photometric effects.
- [Laser-spot stereo measurement workflow](https://archiv.ub.uni-heidelberg.de/volltextserver/10162/1/gruetzmann_phd2009.pdf)
  — spot detection, correspondence and stereo triangulation without dense texture.
- [Laser-spot centroid localization study](https://www.mdpi.com/1424-8220/24/8/2662)
  — threshold/background correction and centroid/local spot fitting.
- [Analytical imaging through refractive interfaces](https://www.sciencedirect.com/science/article/pii/S0143816624005591)
  — why a refractive plate/filter can alter camera-ray geometry.

## 10. Decisions needed before implementation

1. Approve ChArUco as the default new target, retaining chessboard only as fallback.
2. Confirm that “Skip for now” is session-only and never enables metric stereo.
3. Confirm the first physical target is one stationary light, not multiple headlights.
4. Approve the UI split into Main Workflow, Research Validation, Advanced Diagnostics
   and Installation/Hardware Validation.
5. Approve removal of Vehicle Type and the normal-flow daylight phone preset.

Once these decisions are approved, implement Phases A through G in order. Do not start
with appearance tuning or UI deletion before the calibration state model is in place.
