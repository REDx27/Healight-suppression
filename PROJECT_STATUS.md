# GlareTracker — Project Status & Specification

> **Last Updated:** 2026-09-25
> **Python Version:** 3.11.9
> **Platform:** Windows 10/11
> **UI Framework:** PyQt5
> **3D Engine:** PyQtGraph GLViewWidget (OpenGL)

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
│   ├── styles.py               # Dark theme stylesheet (DARK_STYLESHEET)
│   ├── geometry.py             # Pure math: intersection, pixel_to_cm, IPD depth
│   ├── calibration.py          # Camera calibration (single + stereo, save/load .npz)
│   ├── camera.py               # VideoCaptureThread (QThread) — eye tracking
│   ├── headlight_detector.py   # HeadlightDetectorThread (QThread) — stereo bright-spot
│   ├── tracking.py             # TrackingController — business logic coordinator
│   ├── window.py               # MainWindow — layout and signal wiring
│   └── widgets/                # UI panel widgets
│       ├── __init__.py         # Re-exports all widgets
│       ├── video.py            # VideoWidget — live camera feed display
│       ├── windshield_2d.py    # Windshield2DWidget — 2D glare spot overlay
│       ├── scene_3d.py         # Scene3DWidget — OpenGL 3D visualization
│       ├── readout.py          # ReadoutPanel — text telemetry display
│       └── controls.py         # ControlsPanel — parameter inputs, buttons
│
├── calibration/                # Saved .npz calibration files (auto-generated)
├── assets/                     # Application icon (glaretracker-icon.ico)
├── docs/                       # Architecture docs (HTML, PDF)
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
- ✅ **DONE** — Fully implemented and tested
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
| Convert pixel coordinates to real-world cm | ✅ | `geometry.py` — `pixel_to_cm()` (uncalibrated) and `pixel_to_cm_calibrated()` (calibrated) |
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
| Calibrated unprojection (cv2.undistortPoints) | ✅ | `geometry.py` — `pixel_to_cm_calibrated()` |
| Track both eyes individually | ✅ | `camera.py` — `eyes_detected` signal emits left + right 3D positions |
| Depth + yaw displayed on camera feed | ✅ | Green overlay text: "D:XXcm Y:XXdeg" |
| Kalman filter for jitter smoothing | ❌ | Not yet implemented |
| Camera calibration UI (button + dialog) | ❌ | Backend exists in `calibration.py` but no UI to trigger it |

**Key files:** `camera.py`, `geometry.py`, `calibration.py`, `config.py`

---

### REQ-03: Camera Calibration System
**Status: 🔧 PARTIAL** — Backend complete, no GUI

| Sub-requirement | Status | Implementation |
|---|---|---|
| Checkerboard detection (9x6, 2.5cm squares) | ✅ | `calibration.py` — `detect_checkerboard()` with sub-pixel refinement |
| Single camera calibration (intrinsics + distortion) | ✅ | `calibration.py` — `calibrate_single()` returns `CalibrationResult` |
| Stereo camera calibration (R, T, E, F, rectification) | ✅ | `calibration.py` — `calibrate_stereo()` returns `StereoCalibrationResult` |
| Save/load calibration to .npz files | ✅ | `calibration.py` — `save_single_calibration()`, `load_single_calibration()`, etc. |
| Calibrated unprojection helper | ✅ | `calibration.py` — `pixel_to_3d()` and `undistort_point()` |
| Focal length estimation from HFOV | ✅ | `calibration.py` — `estimate_focal_length_from_fov()` |
| Interactive calibration UI dialog | ❌ | No GUI yet; must be called programmatically |

**Key files:** `calibration.py`

---

### REQ-04: Selectable Headlight Detection (Manual / Single / Stereo)
**Status: 🔧 PARTIAL** — implemented; physical camera accuracy testing remains

| Sub-requirement | Status | Implementation |
|---|---|---|
| Bright spot detection (threshold + contours + weighted centroid) | ✅ | `headlight_detector.py` — `detect_bright_spot()` with sub-pixel accuracy |
| Stereo camera synchronization (grab/retrieve pattern) | ✅ | `HeadlightDetectorThread.run()` — `cap1.grab()` + `cap2.grab()` |
| Stereo triangulation to 3D position (cm) | ✅ | Both calibrated (`cv2.undistortPoints` + disparity formula) and uncalibrated fallback |
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
| Render light source(s) (up to 4) | ✅ | `GLScatterPlotItem` with yellow color |
| Render eye-to-light rays (lines) | ✅ | `GLLinePlotItem` |
| Render intersection points on windshield | ✅ | `GLScatterPlotItem` with red color |
| Render camera position indicator | ✅ | `GLScatterPlotItem` |
| Grid floor and axis labels | ✅ | `GLGridItem` |
| Interactive rotation, zoom, pan | ✅ | Built-in pyqtgraph mouse controls |
| Reset view button | ✅ | Resets to distance=140, elevation=20, azimuth=-45 |

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
**Status: ❌ NOT STARTED**

| Sub-requirement | Status | Implementation |
|---|---|---|
| Create lcd_blocker.py module | ❌ | — |
| Fullscreen borderless window on secondary display | ❌ | — |
| White canvas (= transparent on stripped LCD) | ❌ | — |
| Black spots with Gaussian edge softening at intersection pixels | ❌ | — |
| Binocular parallax (2 separate spots per headlight) | ❌ | — |
| Predictive rendering with Kalman filter | ❌ | — |

---

### REQ-13: Data Logging
**Status: ❌ NOT STARTED**

| Sub-requirement | Status | Implementation |
|---|---|---|
| CSV export of eye position, light position, intersections per frame | ❌ | — |
| Session timestamping | ❌ | — |

---

### REQ-14: Standalone Executable
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| PyInstaller build script | ✅ | `scripts/build_exe.ps1` + `scripts/glare_tracker.spec` |
| Single-file .exe with bundled assets | ✅ | `dist/GlareTracker-v1.exe` |
| Custom application icon | ✅ | `assets/glaretracker-icon.ico` |
| Version naming convention (v1, v2, ...) | ✅ | Standalone renamed to `GlareTracker-v1.exe` |

**Key files:** `scripts/build_exe.ps1`, `scripts/glare_tracker.spec`

---

### REQ-15: Silent Launch (No Console Window)
**Status: ✅ DONE**

| Sub-requirement | Status | Implementation |
|---|---|---|
| .pyw launcher using pythonw.exe | ✅ | `GlareTracker.pyw` |
| Windows shortcut with icon | ✅ | `GlareTracker.lnk` in project root |

---

## 6. Architecture Overview

### 6.1 Threading Model

```
Main Thread (Qt Event Loop)
├── MainWindow
│   ├── TrackingController (coordinates all panels)
│   ├── VideoWidget, Scene3DWidget, Windshield2DWidget, ReadoutPanel, ControlsPanel
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
    ├── Stereo triangulation (calibrated or uncalibrated fallback)
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
| `MainWindow` | `window.py` | Layout (QSplitter), signal wiring, thread lifecycle |
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

### High Priority
1. **LCD Light Blocking** (`lcd_blocker.py`) — Render Gaussian-feathered black spots on a stripped TN LCD panel to physically block glare. Must handle binocular parallax (2 spots per headlight).
2. **Calibration UI** — Add a dialog/wizard in the app to run the checkerboard calibration interactively instead of programmatically.
3. **Kalman Filter** — Smooth out eye position jitter for stable intersection tracking.

### Medium Priority
4. **Data Logging** — CSV export of eye, light, and intersection data per frame for research analysis.
5. **Both-Eyes Intersection** — Currently uses midpoint; should compute 2 separate intersection points per headlight for accurate LCD blocking.
6. **Predictive Rendering** — Kalman filter on intersection positions to compensate for ~30-60ms system latency.

### Low Priority
7. **Standalone v2** — Rebuild the PyInstaller executable with all new features.
8. **Settings Persistence** — Save/load user preferences (windshield dimensions, camera positions) between sessions.

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
