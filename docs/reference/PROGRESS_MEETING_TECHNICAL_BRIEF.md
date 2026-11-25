# GlareTracker Progress Meeting Technical Brief

**Project:** Low-Cost Active Windshield Glare Suppression System
**Application:** GlareTracker
**Software version:** 1.3.0 plus the post-release prototype-display integration
**Status date:** 2026-11-25
**Audience:** Project team, supervisor, presentation authors, and AI-assisted study
**Verification at this state:** 196 automated tests passed on Python 3.13; the earlier
1600 x 900 secondary-display Run/Standby/Stop smoke test passed on the connected
monitor.

> **Research boundary:** This is a stationary laboratory prototype. The software can
> track, calculate, visualize, record, and drive a second display, but the complete
> installed camera-to-panel coordinate chain and the stripped-LCD optical performance
> have not yet passed physical validation. It must not be described as a road-ready
> safety system.

---

### Latest operator update - 2026-11-25

Calibrate Center now redraws immediately, discards lost-eye observations and requires
fresh Run-state driver data. Installed-rig positions cannot be shifted with that demo
operation; the tooltip directs the user to the installed rig dialog. Result feedback
stays visible in the status bar across subsequent camera frames.

Driver > Driver Distance has a Live driver distance switch, default OFF. OFF keeps the
entered camera-to-eye optical-axis distance fixed (initially 50 cm), while iris tracking
and drowsiness landmarks stay live. ON restores camera IPD or selected valid ToF depth.
Fixed mode is a bench reference, not measured depth; keep the subject at that distance.
It needs no ToF connection. Settings persist, and changing them clears old observations
and resets the preview centre. The suite now passes 196 tests, including 14 checks
added for these fixes; both switch states were inspected offscreen. No new standalone
build or physical accuracy result is included.

### Previous software milestone - driver and installed-rig calibration, 2026-11-24

Cameras > Calibration now shows the stages required by the chosen mode. Driver
calibration has independent camera/ToF indicators and skips, explicit profile saves
and success alerts, saved-profile reuse, and separate ordered camera and sensor guide
sections. The third dialog fits measured camera-to-LCD poses from off-panel jig
placements and registers the LCD using six measured fit marks and three held-out marks.

Compatible saved poses are applied in live tracking. Road XYZ is reconstructed using
P1/P2, converted from rectified coordinates back through R1, and transformed from raw
LEFT-camera coordinates into LCD centimetres. Driver irises are measured in native
pixels and unprojected using an estimated common eye-plane depth, then transformed into
the same LCD frame. Mirroring is only for preview; installed geometry bypasses the old
demonstration recentering. Profile bindings and per-launch mount/identity confirmation
prevent silent reuse after known setup changes. Physical output checks frame identity,
time pairing and expiry; manual geometry and test patterns remain separate.

The optional USB ToF host path is implemented, including quality/session/clock checks,
range-bias fitting and measured Z offsets. **No controller is attached and no firmware
has been implemented/flashed or physically tested.** Use Skip ToF for camera-only IPD
development. A selected but failed ToF does not silently revert to IPD. Its first fusion
model is restricted to centred, near-frontal faces and does not identify the returning
surface or independently measure each pupil's depth.

44 new synthetic/native-processing/UI tests raise the suite from 138 to 182 passing
tests. Dialog layouts were inspected offscreen. No new physical accuracy result,
installed profile, release version or executable is claimed. See the
[operator guide](../guides/DRIVER_AND_INSTALLED_RIG_CALIBRATION_GUIDE.md) and
[firmware interface](TOF_BRIDGE_PROTOCOL.md). Earlier dated evidence remains history;
the new implementation still needs final mounting and independent measurement.

| File | New calibration responsibility |
|---|---|
| `glare_tracker/installation.py` | Validated records, measured board poses, held-out pose/LCD/range fits, native unprojection and installed stereo conversion |
| `glare_tracker/tof.py` | Optional USB worker, bridge session/quality/clock parsing and bounded camera/range pairing |
| `glare_tracker/widgets/driver_calibration.py` | Camera/ToF dialog, independent skips/saves, capture/reset/reuse and ordered guide |
| `glare_tracker/widgets/rig_calibration.py` | Measured off-panel pose capture, LCD marks, fit validation, evidence and whole-rig save |
| `glare_tracker/window.py` | Mode-aware orchestration, profile readiness, worker/config wiring and timed physical-output authority |

Existing `camera.py`, `headlight_detector.py`, `tracking.py` and `lcd_blocker.py`
apply these records without replacing the core eye/light intersection equation.

## 1. Sixty-second meeting summary

The project attempts to reduce direct glare without darkening the whole windshield.
Two road-facing cameras locate bright sources, a driver-facing camera locates the two
eyes, and the application calculates where every eye-to-light line crosses an LCD
plane. A small dark region should then be rendered at each valid crossing while the
remainder of the panel stays in its most transparent state.

The current application has reached a useful integration milestone:

- the identical road cameras can be assigned as a calibrated LEFT/RIGHT pair;
- their accepted calibration produced 0.173 px and 0.162 px intrinsic RMS, 0.228 px
  stereo RMS, 0.712 px rectified-row p95 error, and a fitted 15.43 cm baseline;
- the measured lens-centre baseline was about 15.35 cm, only 0.08 cm different;
- one, two, and three stationary bright sources have been detected and associated in
  a qualitative live bench test;
- both eyes are retained separately, so two eyes and two lights can create four
  independent ray intersections;
- Run, Standby, and Stop have explicit camera, calculation, and output-display rules;
- a connected non-primary 1600 x 900 monitor is detected and can receive a true
  fullscreen output window;
- the HP ProDisplay P203 active image area is stored as the default physical panel
  profile: 44.28 cm by 24.91 cm;
- Run opens the armed prototype output, while Standby, Stop, display removal, and
  application shutdown clear and release it;
- 196 automated tests pass; the earlier physical multi-monitor lifecycle smoke test passed.

This proves substantial software readiness. It does **not** yet prove centimetre-level
intersection accuracy or optical glare attenuation. Those claims require final rigid
mounting, installed extrinsic calibration, pixel-to-physical mapping, and controlled
ground-truth experiments.

---

## 2. Research objective and system idea

### 2.1 Main objective

Develop and evaluate a low-cost prototype that dynamically places localized LCD dark
regions on the direct line between detected glare sources and the driver's eyes.

### 2.2 Why the system tracks both eyes and every light

A dark region is required where a particular eye-to-light ray crosses the panel. The
system therefore does not calculate one generic centre point.

```text
number of candidate blockers = number of valid eyes x number of valid lights
```

Examples:

| Valid eyes | Valid lights | Maximum separate intersections |
|---:|---:|---:|
| 1 | 1 | 1 |
| 2 | 1 | 2 |
| 2 | 2 | 4 |
| 2 | 3 | 6 |

Nearby blockers may eventually be merged, but the underlying eye/light combinations
must first remain separate so head roll, eye separation, and multiple lamps are not
lost.

### 2.3 Scope boundary

The research does not manufacture a new transparent LCD. It evaluates the glare-
suppression method using a commercially available LCD/controller as the practical
laboratory output component. The original monitor controller receives HDMI from the
laptop. A microcontroller is intended for auxiliary sensors such as the ToF driver-
distance sensor, not for generating the 1600 x 900 video signal.

---

## 3. Agreed physical rig orientation

The permanent cameras do **not** look at the LCD surface.

```text
driver side (-Y)             LCD plane Y=0                 road side (+Y)

driver + ToF  ---> driver        |       road stereo ---> headlights
       [face driver]             |           [face road]
                                 |
                             X left/right
                             Z upward
```

The intended construction is similar to a laptop webcam mounted along the display
edge, except that it uses cameras on both sides:

- mount the two road cameras rigidly on the top bar or rigid frame;
- point both road camera optical axes toward the road;
- keep the road camera sensor planes approximately parallel to the LCD plane;
- keep the two road optical axes approximately perpendicular to the LCD plane and
  parallel to each other; do not deliberately toe them inward;
- mount the driver camera and ToF sensor close together on the driver side;
- point the driver camera and ToF sensor toward the driver's face;
- use the LCD **active pixel area**, not the plastic bezel, as the physical reference;
- mark one permanent frame datum and record the offset from that datum to the active
  pixel edges and every optical centre.

The application frame is:

- origin: bottom-centre of the LCD active area;
- `X`: negative left, positive right;
- `Y`: negative toward the driver, positive toward the road;
- `Z`: zero at the panel bottom, positive upward;
- panel plane: `Y = 0`.

If the final road-camera baseline remains 15.35 cm and the pair is exactly symmetric,
their approximate lateral positions would be `X = -7.675 cm` and `X = +7.675 cm`.
These are only installation starting values. The final measured optical centres and
software calibration determine the accepted camera poses.

---

## 4. Calibration: rig setup versus software calibration

Mechanical measurement and software calibration solve different parts of the problem.

### 4.1 What physical measurement provides

Measurements from the frame provide approximate camera translations, a baseline
cross-check, a repeatable origin, and a way to detect mount movement. They do not
fully reveal lens distortion or small angular mounting errors.

### 4.2 What software calibration provides

Software calibration observes a known flat target and estimates the camera model that
best explains where the target appears in the image. It can measure effective focal
length, principal point, lens distortion, stereo rotation/translation, and installed
camera rotation/translation relative to the panel frame.

### 4.3 Required calibration sequence

Perform these steps after the final frame is rigid and before applying dark camera
filters unless a later filter-verification step is explicitly being run.

1. **Freeze the hardware.** Fix the LCD, camera bars, road stereo baseline, camera
   focus, resolution, and orientation. Mark all mounts.
2. **Measure the rig.** Record active panel width/height, camera optical-centre
   positions, road baseline, ToF offset, and the chosen datum.
3. **Calibrate each road camera's intrinsics.** Show one rigid, completely flat
   checkerboard at many positions, distances, tilts, and image edges. This corrects
   each lens independently.
4. **Calibrate road stereo geometry.** With both cameras fixed, capture the same
   stationary checkerboard simultaneously in both views. This estimates the precise
   LEFT-to-RIGHT rotation and translation used for triangulation.
5. **Calibrate every installed camera to the LCD coordinate frame.** Use a temporary
   rigid checkerboard jig whose 3D pose relative to the marked LCD origin is known.
   The road target is placed on the road side and faces the road cameras. The driver
   target is placed on the driver side and faces the driver camera. Cameras remain in
   their permanent directions.
6. **Calibrate the ToF offset.** Place a stable face-like target at several measured
   driver distances and determine bias, valid range, offset from camera optical centre,
   and failure conditions.
7. **Calibrate LCD pixels to the physical plane.** Display centre, corners, and a grid;
   measure their physical locations; then fit and validate the pixel mapping.
8. **Run held-out validation.** Test poses and positions not used for fitting. Report
   centimetre RMSE, p95, maximum error, dropout, and repeatability.
9. **Lock the profile.** Any camera, focus, resolution, panel, or mount change
   invalidates the associated calibration and requires revalidation.

### 4.4 Temporary calibration jig

The checkerboard should be printed at verified scale and bonded to plywood, acrylic,
foam board, or another rigid flat backing. Loose, curled, folded, or hand-bent paper
breaks the planar-target assumption.

For intrinsic and road-stereo calibration, the board can move freely because the
software estimates its pose in each image. For installed camera-to-panel calibration,
the board pose must be known in the LCD frame. Use a measured rail, slotted stand,
square frame, or other repeatable jig. Record its `X`, `Y`, `Z`, orientation, target
ID, image, and timestamp.

The present camera-to-windshield protocol and CLI were originally written mainly for
visible points on `Y = 0`. Because the final outward-facing cameras cannot directly
view the LCD plane, the guided workflow must be extended to accept measured 3D target
poses on the road and driver sides. The underlying `solvePnP` mathematics supports
general 3D reference points, but the current held-out ray-to-`Y=0` validation and live
profile application still require this integration. This is a known next software
stage, not a completed feature.

---

## 5. Current application behaviour

### 5.1 Startup

1. `run.py` enters `glare_tracker.app.main()`.
2. Qt creates the application and `MainWindow`.
3. The main window builds the 3D scene, 2D panel view, camera cards, telemetry,
   configuration contexts, calibration dialogs, diagnostics recorder, tracking
   controller, and prototype-display window.
4. Camera discovery reads DirectShow device names and probes usable frame modes.
5. The integrated camera is locked to the driver role when selected; the two external
   devices are assigned as road LEFT and RIGHT.
6. Saved camera roles, stereo profile, panel dimensions, target display, clear-state
   choice, and spot radius are restored.
7. If the selected road pair lacks a compatible calibration profile, the application
   offers the guided LEFT, RIGHT, and stereo checkerboard sequence or permits a
   clearly labelled temporary skip.
8. The application enumerates Qt screens and lists only non-primary displays as
   prototype-output targets.

### 5.2 Four operating modes

| Mode | Driver position | Light position |
|---|---|---|
| Fully Auto | Driver camera | Road camera(s) |
| Fully Manual | Manual coordinates | Manual coordinates |
| Driver Position Fixed | Manual coordinates | Road camera(s) |
| Headlight Position Fixed | Driver camera | Manual coordinates |

Driver Position Fixed is particularly useful while evaluating the road cameras because
driver-depth noise cannot be confused with road-stereo error.

### 5.3 Session-state policy

| State | Required cameras | Geometry updates | Prototype output |
|---|---|---|---|
| Run | Active | Active when required coordinates are valid | Fullscreen on selected non-primary display when armed |
| Standby | Kept available for preview | Frozen | Spots cleared, window hidden, desktop released |
| Stop | Released | Cleared | Spots cleared, window hidden, desktop released |

Closing the application also disables the output. Removing/changing the selected
monitor triggers a topology refresh; the application clears the old output and only
reactivates a valid selected target while Run remains active.

### 5.4 Driver processing

The driver worker captures frames outside the GUI thread and uses MediaPipe face/iris
landmarks. It reports the left and right iris positions independently. Depending on
the selected path, depth is a fixed manual value, an experimental IPD-based estimate,
or valid ToF range corrected using measured bias and sensor/eye-plane Z offsets.
The ToF host path exists but still needs MCU firmware and physical testing. Both eyes
use an approximate common optical depth in this first limited-pose fusion model.
Native pixels are undistorted, unprojected and transformed through the installed driver
pose; only the preview is mirrored. Invalid selected ToF suppresses measured output.

Experimental drowsiness monitoring reuses the same landmarks for eye aspect ratio,
long closure, PERCLOS, mouth aspect ratio, and sustained yawning. It is off by default,
is not a clinical or safety-certified alarm, and excludes face-missing frames rather
than falsely counting them as closed eyes.

### 5.5 Road-light processing

The inspectable detector is designed for bright lamps rather than general textured
stereo scenes:

1. acquire both configured road frames;
2. reject obvious colour-bar/test-pattern frames;
3. derive strongest-channel and neutral-light intensity information;
4. calculate multi-scale directional local contrast around bright regions;
5. apply the configured brightness/adaptive threshold;
6. clean candidate masks with blur and morphology;
7. filter by area, saliency, confidence, and optional captured background;
8. retain multiple independent candidates rather than assuming one vehicle layout;
9. associate LEFT/RIGHT candidates with an exact one-to-one minimum-cost assignment;
10. triangulate matched pairs only when a compatible stereo profile is active;
11. use temporal confirmation, smoothing, stable IDs, and short dropout bridging;
12. reject samples older than the configured stale-data limit before geometry.

The **Current Rig - Smooth** preset reproduces the operator's successful high-
suppression settings. **Balanced Stereo Coverage** is a proposed wider-coverage setup
that still requires an A/B physical recording. A smooth-looking track is not by itself
proof of accurate or complete detection.

### 5.6 Rough versus calibrated stereo

Rough mode is allowed only for camera alignment and detection tuning. It can show amber
assumed-depth geometry but cannot authorize physical LCD spots, research measurements,
or an accuracy claim. Calibrated stereo undistorts and rectifies the observations,
matches valid pairs, and triangulates 3D points, but the resulting camera-frame points
use the installed camera-to-LCD transform when its profile is compatible and confirmed.
Actual measurement accuracy still needs physical validation of the entire chain.

### 5.7 Geometry

For eye `E = (x1, y1, z1)` and light `L = (x2, y2, z2)`, the application finds the
point on the line segment where `Y = 0`:

```text
t = -y1 / (y2 - y1)
P = E + t(L - E)
```

The result is accepted only when the ray is not parallel, `0 <= t <= 1`, and the
intersection falls inside the physical panel bounds:

```text
-panel_width/2 <= Px <= panel_width/2
0 <= Pz <= panel_height
```

Each valid physical intersection maps to pixels as:

```text
pixel_x = (Px + panel_width/2) / panel_width * resolution_x
pixel_y = (panel_height - Pz) / panel_height * resolution_y
```

Exact right/bottom physical boundaries are clamped to the last valid zero-based pixel.

### 5.8 Prototype display output

The output workflow now supports the connected 20-inch HP ProDisplay P203:

- default active-area profile: 44.28 cm x 24.91 cm;
- observed Windows/Qt resolution: 1600 x 900;
- named built-in and user-defined physical panel profiles;
- Custom dimensions unlock numeric editing;
- Save requests a name; Remove requests confirmation;
- fullscreen target selection is limited to non-primary displays;
- the native Qt window is explicitly assigned to the chosen `QScreen` before entering
  fullscreen, avoiding accidental placement on the laptop display;
- white clear state is the default hypothesis, with black inverse mode available for
  physical polarity testing;
- Safe Fill, Center Spot, and Corners + Center patterns support alignment checks;
- blocker spots use a configurable radius and feathered edge;
- lost eye, lost light, rough/uncalibrated input, Standby, Stop, display loss, and
  shutdown clear or remove physical output authority.

White is only a software default based on normal LCD behaviour. The stripped panel
must be measured to determine whether white or black actually gives maximum optical
transmission. The physical test result, not the colour name, defines the final safe
state.

---

## 6. Evidence obtained so far

### 6.1 Road-camera calibration evidence

| Measurement | Result | Interpretation |
|---|---:|---|
| LEFT intrinsic RMS | 0.173 px | Passed software fit gate |
| RIGHT intrinsic RMS | 0.162 px | Passed software fit gate |
| Stereo RMS | 0.228 px | Passed software fit gate |
| Rectified-row p95 | 0.712 px | Passed current correspondence gate |
| Fitted stereo baseline | 15.43 cm | Plausible fit result |
| Measured lens-centre baseline | about 15.35 cm | 0.08 cm / about 0.52% difference |
| Frame size | 640 x 480 each | No resolution mismatch |
| Fitted focal-length difference | about 4.5% | Explains the small FOV/zoom difference |

The numbers show that the checkerboard model fits the captured data and that the
estimated baseline is physically plausible. They do not prove held-out headlight-depth
or final panel-intersection accuracy.

### 6.2 Live qualitative evidence

- all three camera roles have operated together;
- the road pair qualitatively detected and associated one, two, and three stationary
  bright sources, including a previously failing upper image region;
- calibrated live tracking appeared smooth with the Current Rig - Smooth preset;
- limited common field of view still caused a source to disappear from one camera near
  some image regions;
- the external monitor was detected as a non-primary 1600 x 900 screen;
- Run opened the fullscreen output on that screen, Standby removed it, Run restored it,
  and Stop removed it again.

### 6.3 Automated evidence

The complete Python 3.13 suite contains 196 passing tests. Coverage includes centre-reference
freshness/redraw, fixed/live driver distance and persistence, as well as geometry
boundaries, camera-role policy, session states, detector behaviour, multiple sources,
stereo fitting/profile guards, calibration UI, recording, stale-data rejection,
extrinsic mathematics, drowsiness state, Blender-style configuration behaviour,
panel profiles, LCD polarity/patterns, and Run/Standby/Stop output lifecycle.

Automated tests verify deterministic software rules. They cannot verify camera optics,
real-world detection accuracy, physical coordinates, transparent-panel attenuation,
external photon-to-display latency, vibration, or environmental robustness.

---

## 7. Implementation status without overclaiming

| Subsystem | Software state | Physical/research state |
|---|---|---|
| Driver face and iris tracking | Implemented | Ground-truth accuracy pending |
| Drowsiness indicators | Experimental implementation | Labelled accuracy/glare trials pending |
| Bright-source detector | Implemented, inspectable, multi-source | Controlled detection-rate trials pending |
| Road intrinsics/stereo calibration | Guided and saved-profile workflow implemented | Fit accepted; held-out depth validation pending |
| Rough stereo | Implemented for setup only | Never measurement authority |
| Stereo triangulation | Installed transform applied with compatible confirmed profiles | Final installed profile and measured accuracy pending |
| Ray-panel intersection | Implemented and unit-tested | End-to-end physical error pending |
| Research CSV/video recording | Implemented | Ten-minute three-camera soak pending |
| Camera-to-panel extrinsic workflow | Measured jig dialog, held-out pose checks, LCD marks and live application implemented | Final physical calibration and independent accuracy pending |
| ToF driver distance | Host serial/calibration/restricted fusion implemented | No controller attached; firmware, wiring and physical measurements pending |
| Secondary-display output | Implemented and live lifecycle tested | Stripped-LCD optics/mapping/latency pending |
| Standalone v1.3 executable | Built from release commit `7dcd958` | Does not yet include this post-release display workflow |

---

## 8. Important code map

### 8.1 Application and UI coordination

| File | Responsibility |
|---|---|
| `run.py` | Source launcher |
| `glare_tracker/app.py` | Creates the Qt application and main window |
| `glare_tracker/window.py` | Main integration layer: widgets, signals, camera ownership, session policy, calibration dialogs, screen discovery, persistence, and shutdown |
| `glare_tracker/widgets/controls.py` | Configuration contexts, operating controls, detector presets, panel profiles, and display-output controls |
| `glare_tracker/widgets/dashboard.py` | Header, camera cards, workspace and sidebar composition |
| `glare_tracker/widgets/scene_3d.py` | 3D visual representation of panel, eyes, lights, rays and intersections |
| `glare_tracker/widgets/windshield_2d.py` | Front-view normalized intersection display |
| `glare_tracker/widgets/readout.py` | Telemetry values and intersection list |
| `glare_tracker/widgets/stereo_calibration.py` | Guided LEFT/RIGHT/stereo chessboard capture and fit UI |
| `glare_tracker/styles.py` | Application-wide Blender-inspired theme rules |

### 8.2 Functional and mathematical core

| File | Responsibility |
|---|---|
| `glare_tracker/tracking.py` | Central business logic joining eyes, lights, geometry, telemetry, diagnostics, 2D/3D views and LCD output |
| `glare_tracker/geometry.py` | Pure ray-plane intersection, pixel/cm conversion, panel-pixel mapping, and IPD-depth functions |
| `glare_tracker/camera.py` | Driver camera worker and MediaPipe eye/face processing |
| `glare_tracker/headlight_detector.py` | Bright-source processing, camera controls, rough/calibrated matching, and road-camera workers |
| `glare_tracker/light_sources.py` | Stable multi-source identities, confidence, smoothing, confirmation and dropout handling |
| `glare_tracker/calibration.py` | Intrinsic/stereo calibration, checkerboard detection, persistence and compatibility |
| `glare_tracker/extrinsics.py` | Rigid transforms, solvePnP, profile fingerprints and validation mathematics |
| `glare_tracker/operating_modes.py` | Explicit four-mode and three-state policy |
| `glare_tracker/diagnostics.py` | Timestamped asynchronous CSV/video research recording |
| `glare_tracker/drowsiness.py` | EAR, PERCLOS, long-closure and yawn metrics |
| `glare_tracker/lcd_blocker.py` | Fullscreen clear state, alignment patterns and physical intersection-to-pixel spots |
| `glare_tracker/config.py` | Shared physical and tracking defaults |

### 8.3 Key design separation

`window.py` is the orchestration layer, not the scientific calculation itself.
`tracking.py`, `geometry.py`, `calibration.py`, `extrinsics.py`, and the detection
modules contain the main functional logic. The `widgets/` files mostly control how
information and settings are presented. This separation allows the algorithms to be
tested and later reused even if the desktop UI changes.

---

## 9. Known limitations and risks

1. **Shared physical frame is not yet validated.** The software applies compatible
   installed transforms; real jig measurements and held-out eye/light/spot tests are
   still needed to establish an accurate LCD coordinate chain.
2. **Installed calibration needs a measured jig.** The final outward-facing cameras
   must see accurately positioned 3D board targets on their own side. The new dialog
   cannot turn freely waved or guessed board coordinates into measured truth.
3. **Driver depth remains weak.** IPD-only depth changes with individual anatomy,
   head yaw, pose, glasses, landmark error, and camera calibration. The ToF comparison
   is intended to reduce this uncertainty.
4. **USB webcams are not hardware synchronized.** Motion between sequential frames can
   become stereo error.
5. **Common field of view limits coverage.** A light visible in only one road camera
   cannot be triangulated. Physical parallelism, overlap, baseline, and camera FOV must
   be optimized together.
6. **Bright-source saturation is useful and harmful.** It isolates the lamp but can
   enlarge the blob, remove centroid detail, create flare, and merge nearby sources.
7. **The smooth preset may hide smaller sources.** Its 656 px minimum area and heavy
   cleanup reduce jitter but can reduce coverage.
8. **White transparency is unverified.** LCD polarity, polarizers, removed layers,
   viewing angle, HDMI loss, and controller reset require bench characterization.
9. **Blocker radius is not yet derived from an error budget.** It currently remains an
   operator setting.
10. **The packaged EXE lags the current source.** `GlareTracker-v1.3.exe` represents
    the release baseline; rebuild only after the present source reaches the next
    stable milestone.

---

## 10. Ordered next work

**Implementation update, 2026-11-24:** The detailed
[installed camera-to-LCD and ToF integration plan](../plans/CAMERA_LCD_AND_TOF_INTEGRATION_PLAN.md)
now defines the implementation sequence, measured-jig workflow, frame/mirroring
rules, live-profile readiness, serial protocol, face-to-eye depth calibration and
test gates. Host calibration and live integration are now implemented; MCU firmware
and physical gates remain open. Validate road alignment with measured fixed eyes
first, then driver pose, then ToF fusion so their errors can be evaluated separately.

1. Build the final rigid LCD/camera frame and record a dimensioned drawing.
2. Mount the road pair parallel to each other and perpendicular to the panel plane;
   mount the driver camera + ToF toward the driver.
3. Reconfirm the saved road calibration after final mounting and filters; recalibrate
   if focus, resolution, order, or rigidity changes.
4. Record Smooth versus Balanced A/B detector runs and measure common-FOV coverage.
5. Complete the ten-minute multi-camera timestamped recording soak.
6. Extend the installed-extrinsic data format/UI to measured 3D checkerboard-jig poses
   and apply compatible transforms in the live pipeline.
7. Implement the selected microcontroller/ToF serial protocol and test bias, dropout,
   ambient-light sensitivity, and camera/ToF spatial offset.
8. Calibrate LCD pixels to physical active-area positions using the built-in test
   patterns and a denser measured grid.
9. Run the end-to-end artificial-eye/light intersection matrix.
10. Derive blocker radius from measured spatial error and latency.
11. Characterize panel transmission, attenuation, response, polarity, viewing angle,
    ghosting, safe state, temperature, and controller failures.
12. Only after those gates, run environmental, vibration, and stationary/closed-course
    experiments under the approved safety plan.

---

## 11. Suggested progress-meeting demonstration

1. Show the application version and configuration contexts.
2. Show the saved road LEFT/RIGHT roles and accepted stereo profile values.
3. Select **Driver Position Fixed** to isolate road tracking.
4. Show one and then two controlled lamps in both road previews.
5. Explain candidate count, matched count, stable source IDs, and why one-camera loss
   prevents valid triangulation.
6. Show the separate eye/light intersection list using manual inputs if live tracking
   is not sufficiently stable for the meeting.
7. Open Prototype Display Output and confirm `DISPLAY2 — 1600×900`.
8. Show Safe Fill, Center Spot, and Corners + Center before any panel disassembly.
9. Demonstrate Run -> fullscreen output, Standby -> desktop restored, Run -> output
   restored, Stop -> desktop restored.
10. End with the implementation-versus-validation table and the ordered next work.

Keep a manual-mode demonstration available. It proves the geometry and display chain
without making the presentation depend on room lighting or webcam behaviour.

---

## 12. Likely examiner questions and concise answers

### Why use two road cameras?

One camera provides a bearing but not general absolute range. A calibrated stereo pair
can triangulate a 3D lamp position from matched observations.

### Why not use LiDAR alone?

LiDAR is useful for vehicle range/shape but does not necessarily identify every actual
emitting headlamp centre. It is a complementary sensor or ground-truth tool, not a
direct replacement for lamp imaging in this low-cost prototype.

### Why use a camera plus ToF for the driver instead of two driver cameras?

The camera is needed for iris position and drowsiness features; the ToF adds direct
distance at lower cost and complexity than driver stereo. Its reliability under head
pose, glasses, ambient infrared, and direct glare still has to be measured. Driver
stereo remains an upgrade if the fused system fails the declared error target.

### Does a low calibration RMS prove the system is accurate?

No. It only shows that the model fits the calibration images. Independent measured
targets not used in fitting are required to establish physical error.

### Why can the two identical cameras still look slightly different?

Identical product housings and resolutions do not guarantee identical effective focal
length. The fitted horizontal focal lengths differed by about 4.5%, so calibration is
needed even for the replacement pair.

### Why do two lights sometimes fail near image edges?

Stereo requires the same source in both camera views. Outside the shared field of view,
or after strong threshold/area filtering, one feed can lose a source and no defensible
3D pair remains.

### Why is the LCD output white when no blocker is required?

White is the initial software hypothesis for maximum transmission through the existing
LCD stack. The application also supports inverse black mode. Bench optical measurements
will select the true clear/safe command.

### Is the system currently safe for a moving vehicle?

No. It is a laboratory prototype. Calibration, physical error, latency, failure
recovery, transparency, thermal, environmental, and hazard validation remain open.

---

## 13. Documents to give an AI or a new teammate

Use these in this order:

1. `docs/reference/PROGRESS_MEETING_TECHNICAL_BRIEF.md` — current, readable meeting
   explanation and code map.
2. `docs/reference/THESIS_AND_DESIGN_REFERENCE.md` — complete design history,
   rationale, algorithms, milestones, validation approach, and thesis material.
3. `PROJECT_STATUS.md` — requirement-level implementation state, limitations, build,
   and verification snapshot.
4. `docs/plans/VALIDATION_PLAN.md` — exact completed/open research gates.
5. `docs/guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md` — how to operate and test the app.
6. `docs/guides/STEREO_CHESSBOARD_SETUP_GUIDE.md` and
   `docs/guides/VISUAL_STEREO_CALIBRATION_GUIDE.md` — road calibration practice.
7. `docs/protocols/CAMERA_TO_WINDSHIELD_CALIBRATION_PROTOCOL.md` and
   `docs/protocols/PHYSICAL_LCD_VALIDATION_PROTOCOL.md` — controlled physical
   calibration and LCD experiments.

Recommended prompt:

```text
Read the supplied GlareTracker documents using this authority order:
PROGRESS_MEETING_TECHNICAL_BRIEF.md, PROJECT_STATUS.md, VALIDATION_PLAN.md,
then THESIS_AND_DESIGN_REFERENCE.md for history. Explain [my question] in simple
language, distinguish implemented software from physically validated results, name
the relevant source files, and do not claim that an open validation stage has passed.
```

For a code question, attach the named source file from Section 8 together with this
brief. For example, attach `tracking.py` and `geometry.py` to understand ray calculation,
or `window.py`, `controls.py`, and `lcd_blocker.py` to understand the second-monitor
workflow.
