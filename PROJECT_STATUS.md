# GlareTracker — Project Status & Specification

> **Last Updated:** 2026-10-27
> **Python Version:** 3.13 (current test environment; 3.11 previously verified)
> **Platform:** Windows 10/11
> **UI Framework:** PyQt5
> **3D Engine:** PyQtGraph GLViewWidget (OpenGL)
> **Source Version:** 1.2.0
> **Reviewed Baseline:** `22517d7` plus the stereo-calibration working tree

---

## 0. Current Status Snapshot

### Active development priority — 2026-10-27

The operator now has **two road cameras plus one driver camera**. The single-road
setup detected a light using a sunglass lens. Both stereo feeds opened, but stereo
operation was unreliable and observed accuracy was poor; no measured accuracy
result is available. The earlier camera-availability blocker is historical.

Next: rigid road-camera mounting, chessboard calibration, and stationary-light
range checks in Driver Position Fixed mode. The app now exposes paired raw-image
capture and intrinsic/stereo fitting, preserves calibration sessions, gates fit
quality, and binds active profiles to camera order and resolution. Uncalibrated
stereo remains preview-only instead of using assumed baseline/focal length. Per-view
candidate and match counts support tuning; irrelevant monocular/manual controls
are hidden in stereo mode, not deleted from other workflows.

**Verification:** 98 automated tests pass on Python 3.13. No new physical validation
has been performed. Live camera-to-windshield transforms and all physical exit
criteria remain outstanding. Follow
[the stereo setup guide](docs/guides/STEREO_CHESSBOARD_SETUP_GUIDE.md), then resume
[the validation plan](docs/plans/VALIDATION_PLAN.md). Earlier dated snapshots below
are retained as history where explicitly labelled.

GlareTracker is currently a **source-level visualization and tracking prototype**, not yet a validated end-to-end physical glare-suppression system. The source contains driver-eye tracking, manual/single-camera/stereo headlight input, ray-plane intersection, 2D/3D visualization, simulation controls, calibration/validation backends, timestamped research recording, and an experimental disabled-by-default secondary-display blocker. Installed-camera and stripped-panel physical validation are still pending.

### Recent changes (through 2026-10-14)

| Area | Current result |
|---|---|
| Headlight input | Manual, single-camera, and stereo modes now support independent tracked-source lists plus custom camera/detector tuning and processing-stage previews |
| Operator workflow | Full-size 3D workspace, Operations/Configuration sidebar, top-ribbon session controls, and collapsible/responsive panels |
| Runtime/UI efficiency | Throttled camera-card rendering, pooled telemetry labels, and cached static windshield graphics |
| Visual system | Standardized blue/green/gray palette, improved vector icons, and a redesigned 3D scene with road context, glass frame, marker glows, and legend |
| Scene usability | Restored the start-of-day 3D scene exactly in dark mode, with an optional high-contrast light-gray canvas, synchronized windshield overlay, and floating controls |
| Window/layout | Screen-aware centered startup size, earlier camera-card stacking, aligned form labels, and corrected windshield title/edge-label placement |
| Camera compatibility | DirectShow/Media Foundation/automatic backend fallback, 640x480 MJPEG compatibility profile, small capture buffers, and camera-index conflict checks |
| Road-light stability | Multi-scale directional saliency at six apparent sizes, adaptive statistical segmentation, confidence filtering, strongest-channel color support, stable IDs, optional captured-background rejection, smoothing, dropout tolerance, and live diagnostics |
| MediaPipe compatibility | Bundled Face Landmarker model and compatibility path for current MediaPipe/Python 3.13 packages while retaining the legacy FaceMesh path |
| Test workflow | Repeatable functional test checklist covering startup, eyes, calibration, geometry, simulation, road detection, end-to-end operation, and shutdown |
| Guided demonstration calibration | Wizard captures stable IPD and lamp-size references, saves camera-specific profiles, enables IPD driver depth and apparent-size road range, and labels estimated versus assumed values |
| Operating policy | Explicit Run/Standby/Stop states and four source modes now control camera ownership, manual inputs, calculations, previews, and movement simulation consistently |
| Automated coverage | 98 tests cover geometry boundaries, mode/state policy, diagnostics/video recording and soak verification, ground-truth analysis, rigid transforms, guarded extrinsic fitting, latency/stale rejection, LCD fail-safe behavior, camera assignment, detector robustness, binocular/multi-light geometry, stereo fitting/profile guards, stable source identity, tuning UI, calibration profiles, and bright-spot observations |
| Recording soak gate | Strict verifier checks finalized duration, timestamp order, exact streams, sidecar/manifest/decode counts, frame gaps/FPS, drops and writer errors |

### Current blockers to the physical prototype

1. Camera-to-windshield fitting, persistence, compatibility checks, and held-out validation tools now exist, but no installed camera has passed the physical target matrix and the profiles are not yet applied by the live pipelines.
2. Road-pair chessboard intrinsic/stereo calibration is now exposed in the UI, but has not yet been validated with the physical pair. Installed-extrinsic calibration is still not integrated into the live pipelines.
3. Separate eye rays and windshield intersections are implemented, but their physical LCD coverage and accuracy have not yet been validated.
4. An experimental secondary-display blocker is implemented, but the stripped panel's optics, mapping, latency, thermal behavior, and safe state are not physically validated.
5. Timestamped CSV/video logging and pipeline timing exist, but there is no Kalman/predictive filtering or settings persistence; automated coverage still cannot validate physical-camera behavior or measurement accuracy.

### Packaging and verification snapshot

- The source reports version **1.2.0**.
- The only local packaged artifact is `dist/GlareTracker-v1.exe`, built on 2026-09-10; it predates the September 25 v1.2 work. The current build script instead produces `dist/GlareTracker.exe`, so a fresh package is required after the next stable milestone.
- This review inspected the tracked source, repository history, dependency list, and available build artifact. The repository contained no uncommitted changes before this notes update.
- Verification on 2026-10-14 passed compilation, all documented validation-script entry points, and 70 automated tests. Coverage includes geometry boundaries, timestamped telemetry/video, ground-truth analysis, rigid/extrinsic transforms, held-out calibration gating, independent physical-intersection analysis, latency/stale rejection, LCD fail-safe behavior, and the earlier detector/session cases. The six-scale detector previously benchmarked at 31.4 FPS on a synthetic 640x480 frame. Physical-camera regression, measurement accuracy, external latency, and stripped-LCD hardware validation remain outstanding.

---

## 1. Project Overview

**GlareTracker** is a real-time windshield glare tracking and suppression system developed as a university research prototype. It tracks a driver's eyes using a webcam, detects oncoming headlight positions, computes where the eye-to-headlight ray intersects the windshield plane, and (in the final phase) renders blocking spots on a stripped LCD panel to physically block glare from reaching the driver's eyes.

### 1.1 Physical Setup (Target Demo)

```
  [Headlight Simulator]          [LCD Panel (no backlight)]        [Driver]
   Bright LED flashlight  --light-->  Bare TN LCD panel    <--eyes--  User
   on a movable stand               (see-through glass)             looking through
        ^                                   ^                          ^
        |                                   |                          |
   Forward Stereo Cams              HDMI secondary output         Driver Webcam
   (2x USB webcams, 25cm apart)     (full-screen OpenCV)        (MediaPipe 3D)
        \                                   |                          /
         +--------------------->  [ Laptop Running GlareTracker ] <---+
                                     Ray-Plane Intersection
                                     LCD Pixel Mapping
```

### 1.2 Coordinate System

- **X axis:** Lateral (left/right), centimetres
- **Y axis:** Depth (front/back), centimetres. Y=0 is the windshield plane. Driver is at negative Y, lights are at positive Y.
- **Z axis:** Vertical height, centimetres

### 1.3 Camera-to-Windshield Measurement Model

For physical positioning, every observation must be expressed in the windshield frame.
After intrinsic calibration and lens correction, pixel `(u, v)` defines a camera ray
`r = K^-1 [u, v, 1]^T`. A depth source supplies the scale `d`, giving camera-space
position `p_camera = d * r`. The installed camera pose must then be applied with the
measured rigid transform `p_windshield = R_wc * p_camera + t_wc`.

- **Driver camera:** one calibrated RGB camera can estimate approximate metric depth
  using a known/per-driver IPD or a canonical face model. It is suitable for prototype
  testing, but universal absolute depth remains scale-sensitive. Stereo or RGB-D is
  preferred for measurement-grade depth.
- **Outdoor camera:** one camera provides a bearing only. Current single-camera mode
  projects that bearing onto a user-supplied distance; calibrated stereo is required
  to measure headlight range from a simultaneous frame pair.
- **Current implementation limitation:** guided one-point profiles and road-pair
  chessboard intrinsic/stereo calibration are available in the UI, but installed
  camera-to-windshield rotation/translation is not yet applied. The
  resulting coordinates remain approximations, not verified physical measurements.

---

## 2. Directory Structure

```
Glare suppression system_test2/
├── run.py                      # Entry point: python run.py
├── GlareTracker.pyw            # Silent launcher (no console window, uses pythonw.exe)
├── GlareTracker.lnk            # Windows shortcut inside project folder
├── requirements.txt            # pip dependencies
├── README.md                   # General readme
├── PROJECT_STATUS.md           # THIS FILE — requirements + implementation status
│
├── glare_tracker/              # Main Python package
│   ├── __init__.py             # Package metadata (version string)
│   ├── __main__.py             # Allows: python -m glare_tracker
│   ├── app.py                  # QApplication bootstrap (main())
│   ├── config.py               # TrackingConfig dataclass (frozen, thread-safe)
│   ├── styles.py               # Centralized application stylesheet (DARK_STYLESHEET)
│   ├── geometry.py             # Pure math: intersection, pixel_to_cm, IPD depth
│   ├── calibration.py          # Camera calibration (single + stereo, save/load .npz)
│   ├── operating_modes.py      # Operating-mode and session-state policy
│   ├── camera.py               # VideoCaptureThread (QThread) — eye tracking
│   ├── headlight_detector.py   # HeadlightDetectorThread (QThread) — stereo bright-spot
│   ├── tracking.py             # TrackingController — business logic coordinator
│   ├── window.py               # MainWindow — layout and signal wiring
│   └── widgets/                # UI panel widgets
│       ├── __init__.py         # Re-exports all widgets
│       ├── video.py            # VideoWidget — live camera feed display
│       ├── windshield_2d.py    # Windshield2DWidget — 2D glare spot overlay
│       ├── scene_3d.py         # Scene3DWidget — OpenGL 3D visualization
│       ├── dashboard.py        # Header, camera cards, workspace, tabbed sidebar
│       ├── icons.py            # Consistent dependency-free vector icon set
│       ├── readout.py          # ReadoutPanel — text telemetry display
│       ├── controls.py         # ControlsPanel — parameter inputs, buttons
│       └── calibration_wizard.py # Guided driver/road distance calibration
│
├── tests/                      # Automated policy, session, and calibration tests
├── calibration/                # Saved .npz calibration files (auto-generated)
├── assets/                     # Application icon (glaretracker-icon.ico)
├── docs/                       # Indexed plans, guides, protocols, and references
├── dist/                       # Standalone executables
│   └── GlareTracker-v1.exe     # Standalone build v1 (PyInstaller)
├── scripts/                    # Build scripts
│   ├── build_exe.ps1           # PowerShell script to build .exe via PyInstaller
│   └── glare_tracker.spec      # PyInstaller spec file
└── .gitignore
```

---

## 3. Dependencies

```
PyQt5>=5.15          # GUI framework
opencv-python>=4.8   # Camera capture, image processing, calibration
mediapipe>=0.10      # Face mesh / iris landmark detection
numpy>=1.24          # Numerical computation
pyqtgraph>=0.13      # OpenGL-based 3D scene rendering
PyOpenGL>=3.1        # OpenGL bindings for pyqtgraph
pyinstaller>=6.0     # Standalone executable builder (dev dependency)
```

Install: `pip install -r requirements.txt`

---

## 4. How to Run

```bash
# Standard launch
python run.py

# Silent launch (no console window on Windows)
pythonw GlareTracker.pyw

# As a module
python -m glare_tracker

# Standalone executable (no Python needed)
dist/GlareTracker-v1.exe
```

---

## 5. Requirements & Implementation Status

### Legend
- ✅ **DONE** — Implementation is present and was previously marked complete; this review did not re-run software or hardware validation
- 🔧 **PARTIAL** — Core logic exists but not fully integrated or polished
- ❌ **NOT STARTED** — Planned but no code written yet

---

### REQ-01: Real-Time Eye Tracking via Webcam
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Capture webcam video at 30 FPS | ✅ | `camera.py` — `VideoCaptureThread(QThread)` using `cv2.VideoCapture` with `CAP_DSHOW` backend |
| Run in background thread (non-blocking UI) | ✅ | `QThread` with `frame_ready`, `eye_detected`, `eye_lost` signals |
| Detect iris position using MediaPipe Face Mesh | ✅ | Landmarks 468 (right iris) and 473 (left iris) with `refine_landmarks=True` |
| Convert pixel coordinates to real-world cm | 🔧 | `geometry.py` provides fallback and intrinsic-unprojection paths; camera-to-windshield extrinsics are still required for verified physical coordinates |
| Draw iris overlay on camera feed | ✅ | Red filled circle at midpoint, blue circles at each iris |
| Mirror the video feed for natural interaction | ✅ | `cv2.flip(frame, 1)` |

**Key files:** `camera.py`, `geometry.py`

---

### REQ-02: Improved Eye Tracking with Depth Estimation
**Status: 🔧 PARTIAL** — Core algorithms implemented, calibration UI not yet integrated

| Sub-requirement | Status | Implementation |
|---|---|---|
| IPD-based depth estimation (Z = IPD_real * f / IPD_pixels) | ✅ | `geometry.py` — `estimate_ipd_depth()` with yaw correction |
| Head pose estimation via solvePnP | ✅ | `camera.py` — `_estimate_head_pose()` using 6 anthropometric face model points |
| Calibrated unprojection (cv2.undistortPoints) | 🔧 | Intrinsic ray conversion exists in `geometry.py`; installed camera rotation/translation into the windshield frame is not yet applied |
| Track both eyes individually | ✅ | `camera.py` — `eyes_detected` signal emits left + right 3D positions |
| Depth + yaw displayed on camera feed | ✅ | Green overlay text: "D:XXcm Y:XXdeg" |
| Kalman filter for jitter smoothing | ❌ | Not yet implemented |
| Camera calibration UI (button + dialog) | ❌ | Backend exists in `calibration.py` but no UI to trigger it |

**Key files:** `camera.py`, `geometry.py`, `calibration.py`, `config.py`

---

### REQ-03: Camera Calibration System
**Status: 🔧 PARTIAL** — road-pair chessboard and demonstration workflows available; physical validation and installed-extrinsic integration remain

| Sub-requirement | Status | Implementation |
|---|---|---|
| Checkerboard detection (9x6, 2.5cm squares) | ✅ | `calibration.py` — `detect_checkerboard()` with sub-pixel refinement |
| Single camera calibration (intrinsics + distortion) | ✅ | `calibration.py` — `calibrate_single()` returns `CalibrationResult` |
| Stereo camera calibration (R, T, E, F, rectification) | ✅ | `calibration.py` — `calibrate_stereo()` returns `StereoCalibrationResult` |
| Save/load calibration to .npz files | ✅ | `calibration.py` — `save_single_calibration()`, `load_single_calibration()`, etc. |
| Calibrated unprojection helper | ✅ | `calibration.py` — `pixel_to_3d()` and `undistort_point()` |
| Focal length estimation from HFOV | ✅ | `calibration.py` — `estimate_focal_length_from_fov()` |
| Guided IPD driver-depth reference | ✅ | Wizard captures stable iris separation at a measured distance and saves a camera-specific focal-scale profile |
| Guided monocular road reference | ✅ | Wizard captures one lamp at known range and saves an apparent-size range profile with threshold and resolution metadata |
| Road-pair intrinsic/stereo UI | ✅ | Paired chessboard capture, fit diagnostics, raw evidence and ordered-camera profiles; physically unvalidated |
| Standalone driver intrinsics / installed-extrinsic UI | ❌ | Backends remain outside the guided road-pair workflow |

**Key files:** `calibration.py`

---

### REQ-04: Selectable Headlight Detection (Manual / Single / Stereo)
**Status: 🔧 PARTIAL** — implemented; physical camera accuracy testing remains

| Sub-requirement | Status | Implementation |
|---|---|---|
| Bright spot detection (threshold + contours + weighted centroid) | ✅ | `headlight_detector.py` — `detect_bright_spot()` with sub-pixel accuracy |
| Independent multiple-light detection | ✅ | Variable candidate list with stable IDs, timestamps, confidence, state, and per-source geometry |
| Custom detection tuning | ✅ | Optional exposure/brightness/contrast/gain and software threshold/area/blur/cleanup/source/matching controls |
| Processing preview selector | ✅ | Road-feed dropdown switches among overlay, original, threshold mask, grayscale, and blurred grayscale |
| Controlled-scene background rejection | ✅ | Operator captures the static scene without the test lamp; detection then requires a configurable bright change, suppressing windows and other stationary bright regions |
| Camera-control readback | ✅ | UI reports requested versus camera-reported exposure and indicates when the driver rejects a manual setting |
| Detected-camera role assignment | ✅ | Refreshable dropdowns list cameras that successfully return frames; driver and one/two headlight roles are assigned independently |
| Paired stereo capture (grab/retrieve pattern) | ✅ | Sequential grabs, NOT hardware-synchronized exposures |
| Stereo triangulation to 3D position (cm) | ✅ | Compatible calibration required; rectified-point matching and disparity depth, otherwise previews only |
| Manual low exposure to isolate light source | ✅ | `CAP_PROP_EXPOSURE = -8`, `CAP_PROP_AUTO_EXPOSURE = 0.25` |
| MJPG compression for USB bandwidth | ✅ | `FOURCC = MJPG` on both cameras |
| Side-by-side stereo feed display in UI | ✅ | `window.py` — `stereo_view` QLabel updated via `frame_ready` signal |
| Auto-populate light position sliders | ✅ | `window.py` — `_on_auto_headlight()` updates spin-boxes with signal blocking |
| Toggle between manual and auto-detect | ✅ | `controls.py` — Manual/Auto selector disables coordinate inputs in Auto mode |
| Coordinate remapping (camera space to GlareTracker global space) | ✅ | X=lateral, Y=depth, Z=height relative to the windshield top-centre |
| Manual / Auto source selection | ✅ | Manual uses entered coordinates; Auto starts the selected detector |
| Single outdoor-camera mode | ✅ | Bright-spot pixel is projected at a configurable assumed depth and HFOV |
| Single / Stereo setup selector | ✅ | Auto Camera Setup panel switches between one- and two-camera detection |
| Camera index selection | ✅ | Driver, primary outdoor, and secondary stereo indices are configurable |
| Live camera previews and availability messages | ✅ | Compact driver/outdoor feeds show connected, unavailable, or no-light state |
| Default camera origin | ✅ | Camera model defaults to the windshield top-centre `(0, 0, windshield height)` |

**Key files:** `headlight_detector.py`, `window.py`, `controls.py`

---

### REQ-05: 3D Scene Visualization
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| OpenGL 3D view embedded in PyQt5 | ✅ | `scene_3d.py` — `Scene3DWidget` using `pyqtgraph.opengl.GLViewWidget` |
| Render windshield plane (rectangle at Y=0) | ✅ | `GLMeshItem` with dynamic width/height |
| Render driver eye position (sphere/point) | ✅ | `GLScatterPlotItem` |
| Render light source(s) (up to 8) | ✅ | `GLScatterPlotItem` with yellow color |
| Render eye-to-light rays (lines) | ✅ | `GLLinePlotItem` |
| Render intersection points on windshield | ✅ | Layered amber/yellow `GLScatterPlotItem` markers |
| Render camera position indicator | ✅ | `GLScatterPlotItem` |
| Grid floor and axis labels | ✅ | `GLGridItem` |
| Interactive rotation, zoom, pan | ✅ | Built-in pyqtgraph mouse controls |
| Reset view button | ✅ | Resets to the original scene view: distance=145, elevation=22, azimuth=-45 |

**Key files:** `widgets/scene_3d.py`

---

### REQ-06: 2D Windshield View
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Top-down 2D rectangle representing windshield | ✅ | `windshield_2d.py` — custom QPainter widget |
| Glowing glare spots at intersection positions | ✅ | Radial gradient circles with glow effect |
| In-bounds / out-of-bounds visual distinction | ✅ | Green for in-bounds, red for out-of-bounds; warning text overlay |
| Dynamic aspect ratio matching windshield dimensions | ✅ | `set_windshield_aspect()` |

**Key files:** `widgets/windshield_2d.py`

---

### REQ-07: Telemetry Readout Panel
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Live eye position display (X, Y, Z) | ✅ | `readout.py` — `ReadoutPanel` |
| Live intersection coordinates | ✅ | With in-bounds/out-of-bounds color coding |
| FPS counter | ✅ | Updated every 1 second |
| Tracking status indicator | ✅ | ACTIVE/TRACKING/NO FACE/STOPPED states |
| Light source count and vehicle type | ✅ | Shows "2 source(s) — Four-Wheeler/Car" |

**Key files:** `widgets/readout.py`

---

### REQ-08: Controls Panel
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Windshield dimension inputs (W, H in cm) | ✅ | `QDoubleSpinBox` with 0.5 step |
| Camera position inputs (X, Y, Z) | ✅ | Three spin boxes |
| Driver distance input | ✅ | Used as fallback depth when uncalibrated |
| Light source position inputs (X, Y, Z) | ✅ | Three spin boxes, disabled during auto-detect |
| Vehicle category selector (Motorcycle/Car/Extreme) | ✅ | `QComboBox` — generates 1/2/4 light sources |
| Light movement simulation (3 modes) | ✅ | Coming straight, opposite side, long distance |
| Start/Stop stream button | ✅ | Checkable toggle button |
| Calibrate center button | ✅ | Captures current eye position as baseline |
| Reset 3D view button | ✅ | Resets camera to default angle |
| Stereo auto-detect toggle | ✅ | `QCheckBox` that starts/stops headlight thread |

**Key files:** `widgets/controls.py`

---

### REQ-09: Intersection Calculation (Ray-Plane)
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Parametric ray from eye to light | ✅ | `geometry.py` — `compute_intersection()` |
| Intersection with windshield plane (Y=0) | ✅ | Returns (x, 0.0, z) or None |
| Bounds checking against windshield dimensions | ✅ | `tracking.py` — checks -W/2 <= x <= W/2 and 0 <= z <= H |
| Multiple lights (1-4 simultaneous intersections) | ✅ | Loop over all light positions |
| Intersection-to-LCD-pixel mapping | ✅ | `geometry.py` — `intersection_to_pixel()` |

**Key files:** `geometry.py`, `tracking.py`

---

### REQ-10: Light Movement Simulation
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| "Coming straight" animation | ✅ | Light approaches along Y axis with slight X oscillation |
| "Coming at the opposite side" animation | ✅ | Light sweeps laterally across 180cm |
| "Long distance" animation | ✅ | Light starts at Y+700 and approaches to Y+120 |
| Play/Stop toggle | ✅ | QTimer at 50ms interval driving phase advance |
| Multi-light animation (vehicle offsets preserved) | ✅ | All lights in cluster move relative to centroid |

**Key files:** `tracking.py`

---

### REQ-11: Calibration Baseline
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Auto-capture baseline on first face detection | ✅ | `tracking.py` — `_capture_baseline()` |
| Manual re-calibrate button | ✅ | Sets current observed eye position as center reference |
| Offset subtraction from all subsequent frames | ✅ | X and Z offsets stored in `_calibration_offset` |

**Key files:** `tracking.py`

---

### REQ-12: LCD Light Blocking Prototype
**Status: 🔧 PARTIAL** — software renderer implemented; physical panel validation pending

| Sub-requirement | Status | Implementation |
|---|---|---|
| Create lcd_blocker.py module | ✅ | Disabled-by-default `LCDBlockerWindow` |
| Fullscreen borderless window on secondary display | ✅ | Explicit enable requires a detected secondary screen |
| White canvas (= transparent on stripped LCD) | ✅ | Software safe state; physical polarity/transparency still requires validation |
| Black spots with Gaussian edge softening at intersection pixels | ✅ | Radial feathering with bounded pixel mapping |
| Binocular parallax (2 separate spots per headlight) | ✅ | Consumes all valid per-eye/per-light intersections |
| Predictive rendering with Kalman filter | ❌ | — |

---

### REQ-13: Data Logging
**Status: ✅ IMPLEMENTED IN SOURCE** — physical soak validation pending

| Sub-requirement | Status | Implementation |
|---|---|---|
| CSV export of eye position, light position, intersections per frame | ✅ | Asynchronous `telemetry.csv` with ground-truth and pipeline events |
| Session timestamping | ✅ | UTC plus monotonic nanoseconds; video-frame sidecar timestamps |
| Camera preview video | ✅ | Driver/primary/secondary MJPEG streams with per-frame CSV |
| Session metadata and health | ✅ | `session.json` records configuration, frames, drops, and errors |

---

### REQ-14: Standalone Executable
**Status: 🔧 PARTIAL** — build pipeline exists, but the v1.2 source has not been packaged

| Sub-requirement | Status | Implementation |
|---|---|---|
| PyInstaller build script | ✅ | `scripts/build_exe.ps1` + `scripts/glare_tracker.spec` |
| Single-file .exe with bundled assets | ✅ | Confirmed by the older local `dist/GlareTracker-v1.exe` build |
| Custom application icon | ✅ | `assets/glaretracker-icon.ico` |
| Package current v1.2 source | ❌ | Current build script targets `dist/GlareTracker.exe`; a fresh build and launch test are still required |

**Key files:** `scripts/build_exe.ps1`, `scripts/glare_tracker.spec`

---

### REQ-15: Silent Launch (No Console Window)
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| .pyw launcher using pythonw.exe | ✅ | `GlareTracker.pyw` |
| Windows shortcut with icon | ✅ | `GlareTracker.lnk` in project root |

---

### REQ-16: Advanced Operator UI Architecture
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Centralized visual design system | ✅ | `styles.py` — immutable palette tokens and `ThemeManager` stylesheet generation |
| Reusable dashboard components | ✅ | `dashboard.py` — header, status badge, camera card, workspace, and sidebar classes |
| Operations / configuration separation | ✅ | Tabbed sidebar keeps live telemetry distinct from setup controls |
| Full-size 3D workspace | ✅ | 3D scene is the primary view with a responsive intersection overlay |
| Live system-state header | ✅ | Displays application version, Manual/Auto mode, and tracking state |
| Ribbon session controls | ✅ | Start/stop, centre calibration, and 3D reset are always available in the top application ribbon |
| Responsive sidebar navigation | ✅ | Operations and Configuration tabs expand equally, elide safely, and receive additional working width |
| Neutral layered application chrome | ✅ | Graphite canvas, raised surfaces, and stronger neutral borders visually separate the workspace, sidebar, cards, and inputs without a blue wash |
| Cohesive interaction hierarchy | ✅ | Blue identifies navigation, focus, and primary actions; green identifies active/success states; gray structures surfaces, borders, and secondary text |
| Efficient preview rendering | ✅ | Camera cards cache frames and cap preview scaling to 20 FPS |
| Responsive camera layout | ✅ | Camera cards switch between horizontal and vertical layouts based on sidebar width |
| Collapsible operations panel | ✅ | Header PANEL control releases additional space for the 3D workspace |
| Allocation-free telemetry updates | ✅ | Intersection labels are pooled and updated instead of recreated every frame |
| Cached windshield rendering | ✅ | Static gradients, grid, labels, and outline are repainted only when geometry/state changes |
| High-DPI support | ✅ | Qt high-DPI scaling and pixmaps enabled before application startup |

**Key files:** `styles.py`, `widgets/dashboard.py`, `window.py`, `app.py`

---

### REQ-17: Vector Icon System & Modern 3D Graphics
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Consistent vector icons | ✅ | `icons.py` renders scalable Qt-native line icons without third-party packages |
| Action and mode iconography | ✅ | Stream, simulation, calibration, reset, panel, tabs, cameras, and scene controls use shared icons |
| Recovered spatial palette | ✅ | Start-of-day deep navy scene with cyan windshield, amber lights, orange/yellow intersections, red rays, blue eye marker, and a coordinated light-gray canvas option |
| Translucent windshield glass | ✅ | Low-alpha OpenGL mesh with a separate high-contrast cyan frame |
| Spatial driving context | ✅ | Restored the layered minor/major grids plus road-edge and centre reference lines from the start-of-day scene |
| Layered tracked markers | ✅ | Eye, headlight, camera, and intersection points use separate glow and core layers |
| In-scene legend | ✅ | Compact overlay identifies driver, light, intersection, and windshield colors |
| Modern scene controls | ✅ | Dedicated gear settings control plus sun/moon dark/light-gray canvas toggle inside the 3D workspace |

**Key files:** `widgets/icons.py`, `widgets/scene_3d.py`, `widgets/controls.py`, `widgets/dashboard.py`

---

## 6. Architecture Overview

### 6.1 Threading Model

```
Main Thread (Qt Event Loop)
├── MainWindow
│   ├── TrackingController (coordinates all panels)
│   ├── ApplicationHeader, SceneWorkspace, OperationsSidebar, CameraPreviewCard
│   ├── Scene3DWidget, Windshield2DWidget, ReadoutPanel, ControlsPanel
│   └── QTimers: FPS update (1s), movement animation (50ms)
│
├── VideoCaptureThread (QThread)
│   ├── cv2.VideoCapture (camera index 0)
│   ├── MediaPipe FaceMesh (refine_landmarks=True)
│   ├── Emits: frame_ready, eye_detected, eyes_detected, eye_lost
│   ├── Emits: depth_updated, head_pose_updated (when calibrated)
│   └── Supports: uncalibrated mode (pixel_to_cm) and calibrated mode (solvePnP + IPD)
│
└── HeadlightDetectorThread (QThread)
    ├── cv2.VideoCapture x2 (camera indices 1, 2)
    ├── detect_bright_spot() — threshold + weighted centroid
    ├── Stereo triangulation (compatible calibration required; otherwise previews only)
    └── Emits: frame_ready, headlight_detected, headlight_lost
```

### 6.2 Data Flow

```
Webcam (cam 0) → VideoCaptureThread → eye_detected signal
                                         ↓
                                  TrackingController.on_eye_detected()
                                         ↓
                                  compute_intersection(eye, light)
                                         ↓
                              ┌──────────┼──────────┐
                              ↓          ↓          ↓
                        Scene3DWidget  Windshield2D  ReadoutPanel

Stereo cams (cam 1+2) → HeadlightDetectorThread → headlight_detected signal
                                                      ↓
                                              MainWindow._on_auto_headlight()
                                                      ↓
                                              Updates light X/Y/Z spin-boxes
                                                      ↓
                                              TrackingController.on_params_changed()
```

### 6.3 Key Classes

| Class | File | Responsibility |
|---|---|---|
| `TrackingConfig` | `config.py` | Frozen dataclass — thread-safe parameter snapshot |
| `VideoCaptureThread` | `camera.py` | Background webcam + MediaPipe + eye tracking |
| `HeadlightDetectorThread` | `headlight_detector.py` | Background stereo camera + bright-spot triangulation |
| `TrackingController` | `tracking.py` | Business logic: calibration, intersection, simulation, FPS |
| `MainWindow` | `window.py` | Application composition, signal wiring, and thread lifecycle |
| `SceneWorkspace` | `widgets/dashboard.py` | Full-size 3D viewport with responsive intersection overlay |
| `CameraPreviewCard` | `widgets/dashboard.py` | Throttled camera rendering and semantic device status |
| `OperationsSidebar` | `widgets/dashboard.py` | Separates live operations from configuration controls |
| `ThemeManager` | `styles.py` | Generates the stylesheet from centralized design tokens |
| `IconFactory` | `widgets/icons.py` | Renders the shared vector icon set with Qt painting primitives |
| `CalibrationResult` | `calibration.py` | Holds camera_matrix, dist_coeffs, focal_length, etc. |
| `StereoCalibrationResult` | `calibration.py` | Holds stereo R, T, E, F, rectification matrices |

### 6.4 Key Functions

| Function | File | Purpose |
|---|---|---|
| `compute_intersection(eye, light)` | `geometry.py` | Ray-plane intersection at Y=0 |
| `pixel_to_cm(...)` | `geometry.py` | Uncalibrated pixel-to-cm conversion |
| `pixel_to_cm_calibrated(...)` | `geometry.py` | Calibrated conversion with lens correction |
| `estimate_ipd_depth(...)` | `geometry.py` | Depth from inter-pupillary distance |
| `intersection_to_pixel(...)` | `geometry.py` | Map 3D intersection to LCD pixel coords |
| `detect_bright_spot(frame)` | `headlight_detector.py` | Find brightest spot with sub-pixel centroid |
| `detect_checkerboard(frame)` | `calibration.py` | Find checkerboard corners with sub-pixel refinement |
| `calibrate_single(frames)` | `calibration.py` | Run single-camera calibration |
| `calibrate_stereo(frames1, frames2)` | `calibration.py` | Run stereo calibration |

---

## 7. Configuration Defaults (TrackingConfig)

| Parameter | Default | Unit | Description |
|---|---|---|---|
| `screen_w_cm` | 34.5 | cm | Windshield width |
| `screen_h_cm` | 19.5 | cm | Windshield height |
| `eye_dist_cm` | 50.0 | cm | Fallback driver distance (uncalibrated mode) |
| `camera_x_cm` | 0.0 | cm | Camera lateral offset |
| `camera_y_cm` | 0.0 | cm | Camera depth offset |
| `camera_z_cm` | 19.5 | cm | Camera height; top edge of default windshield |
| `ipd_cm` | 6.3 | cm | Inter-pupillary distance (human average) |
| `use_calibration` | False | bool | Whether to use calibrated intrinsics |

---

## 8. Remaining Work (Roadmap)

Recommended execution order follows the active validation plan. Software readiness is
not treated as a physical test pass.

### High Priority
1. **Dual-Camera Logging Soak** — Connect a second camera and complete the ten-minute timestamped CSV/video recording exit check.
2. **Ground-Truth Baselines** — Measure driver-eye and road-light accuracy, jitter, availability, and dropouts with fixed mounts and repeated positions.
3. **Installed Extrinsic Validation** — Fit, apply, and physically validate each camera-to-windshield profile using independent held-out targets.
4. **End-to-End Intersection Validation** — Compare the implemented per-eye/per-light intersections with independently marked physical windshield crossings.
5. **Physical LCD Bench Validation** — Characterize the implemented secondary-display blocker, pixel mapping, attenuation, response, temperature, and transparent fail-safe state.

### Medium Priority
6. **Latency and Failure Recovery** — Execute the instrumented software timing matrix, external photon-to-display measurement, and failure-injection protocol.
7. **Environmental Validation** — Run the phased illumination, weather-like, thermal, vibration, endurance, and stationary vehicle-like tests after earlier gates pass.
8. **Measurement-Grade Calibration UI** — Expose checkerboard intrinsic, stereo, and installed-extrinsic workflows after the scripted physical process is proven.
9. **Filtering and Prediction** — Add Kalman/predictive rendering only after measured jitter and latency establish the required model and acceptance limits.

### Low Priority
10. **Standalone v1.2+** — Rebuild and launch-test the PyInstaller executable after the next stable feature milestone.
11. **Settings Persistence** — Save/load user preferences (windshield dimensions, camera positions) between sessions.

The detailed checkboxes, exit criteria, and evidence paths are maintained in
`docs/plans/VALIDATION_PLAN.md`.

---

## 9. Hardware Requirements

| Item | Purpose | Notes |
|---|---|---|
| Laptop with webcam | Driver eye tracking (cam 0) | 640x480 at 30 FPS minimum |
| 2x USB webcams | Stereo headlight detection (cam 1, cam 2) | 720p, mounted 25cm apart |
| LED flashlight | Headlight simulator | Any bright focused light |
| 20-24" TN monitor | LCD light blocker (strip backlight) | TN type only (fails transparent) |
| HDMI-to-LVDS controller board | Drive stripped LCD from laptop | ~$15 |
| Printed checkerboard | Camera calibration | 9x6 inner corners, 2.5cm squares, on rigid cardboard |

---

## 10. Prior Art & References

- **Bosch Virtual Visor** (CES 2020) — Transparent LCD sun visor with eye tracking
- **CMU Programmable Automotive Headlights** (SIGGRAPH 2012) — Active shadow projection
- Ungureanu et al., "A Novel Approach against Sun Glare to Enhance Driver Safety" (2018)
- US Patent US10562470B2 (Robert Bosch GmbH) — Active LCD shading system
- US Patent US8589034B2 — Automated glare-blocking windshield system
