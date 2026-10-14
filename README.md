# GlareTracker

GlareTracker is a Windows desktop application that tracks driver eye position from a webcam and visualizes glare intersections on a virtual windshield.

The documentation map and source-of-truth order are in
[docs/README.md](docs/README.md). Long-form design history, implementation rationale,
validation methodology, and later-thesis material are in
[docs/reference/THESIS_AND_DESIGN_REFERENCE.md](docs/reference/THESIS_AND_DESIGN_REFERENCE.md).

Driver and headlight coordinates can each come from a camera or a fixed manual value.
The four explicit operating modes are Fully Auto, Fully Manual, Driver Position Fixed,
and Headlight Position Fixed. Run enables calculations, Standby keeps required previews
live while calculations are frozen, and Stop releases all cameras. Road tracking
supports a single-camera estimate or a calibrated/fallback stereo setup.

Version 1.1 introduces an operator-focused dashboard with a full-size 3D workspace,
responsive windshield-intersection overlay, live system-state header, reusable camera
cards, and separate Operations and Configuration tabs. UI colors and component states
are driven by a centralized theme system. Camera cards reflow for narrow layouts, the
operations sidebar can be collapsed from the header, and static overlay graphics plus
telemetry widgets are cached/reused to reduce work during real-time tracking.

Version 1.2 adds a dependency-free vector icon system and a redesigned spatial view:
translucent framed windshield glass, layered navigation grids, road/lane context,
glowing eye/light/intersection markers, refined ray traces, and an in-scene legend.
Session, calibration, and 3D-reset actions now live in the top ribbon, while the
Operations and Configuration tabs use equal-width responsive navigation.
The surrounding application chrome follows a cohesive simulation-studio style:
layered blue-gray surfaces, blue navigation/focus accents, and green active/success
states. The 3D workspace includes a dark/light-gray canvas toggle, coordinated windshield
overlay, the restored layered navigation grid and marker palette from the start-of-day
scene, and responsive scene controls.

## Current development status

As of 2026-10-14, the source is version 1.2.0. The tracking, headlight-input,
intersection, simulation, and visualization paths are implemented in source. Camera
capture now includes Windows backend fallback, a low-bandwidth 640x480 MJPEG profile,
adaptive bright-source detection, temporal light tracking, dropout tolerance, and
MediaPipe Tasks compatibility for Python 3.13. Seventy automated tests cover geometry,
mode/state, session, calibration profiles, extrinsic fitting, diagnostics, latency,
LCD fail-safe behavior, and detection policies; the validation plan records the
remaining physical-camera and optical checks.

The current demonstration uses camera 0 for the driver and camera 1 for the road view.
Single-camera road tracking measures a light bearing and, without a saved demonstration
profile, projects it at an operator-supplied distance. The guided calibration wizard can
instead estimate driver depth from measured IPD and estimate road-light range from the
apparent size of one reference lamp. Remaining physical-system work includes camera-to-
windshield extrinsic measurement/application, physical validation of the new
left/right-eye intersections, stripped-panel optical validation, prediction, and the
ordered ground-truth/environmental test campaigns. Timestamped CSV/video recording
and an experimental disabled-by-default secondary-display blocker now exist in source.

The local `dist/GlareTracker-v1.exe` artifact predates the v1.2 source changes. Run the
build script and launch-test the resulting `dist/GlareTracker.exe` before treating the
latest source as a distributable release. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for
the reviewed implementation matrix, limitations, verification state, and ordered
roadmap.

## Positioning accuracy

The current uncalibrated driver-camera mode is a visualization fallback: it maps the
iris position across the configured windshield size and uses a fixed driver distance.
The optional intrinsic-calibration path corrects lens distortion and estimates depth
from interpupillary distance, but a complete physical installation must also calibrate
the rigid camera-to-windshield transform (rotation and translation). Until that
extrinsic calibration is added, reported centimetre coordinates must not be treated as
measurement-grade windshield coordinates.

A single calibrated driver camera is suitable for prototype tracking when each driver
is calibrated (especially IPD) and the result is validated over the expected seating
range. Stereo or an RGB-D camera is recommended when robust absolute depth is required.
For the outdoor light camera, a single image supplies direction but not independently
measured range; single-camera mode therefore requires the configured distance. Use the
stereo setup for measured 3D headlight position.

## Guided single-camera demonstration calibration

Open **Configuration → Single-Camera Calibration → Calibrate Single-Camera Distances** with
the integrated driver camera on index 0 and USB road camera on index 1. The wizard starts
the required feeds and provides three guided pages:

1. **Driver reference:** enter measured IPD and lens-to-eye distance, face the camera,
   hold still, and capture at least 20 stable iris-separation samples. The saved focal
   scale enables the pinhole estimate `distance = IPD × focal / iris_pixels`.
2. **Road reference:** place the same demonstration lamp at a measured distance, keep it
   centred and steady in a dim scene, and capture at least 20 stable bright-core diameter
   samples. Live range uses `distance = reference_distance × reference_diameter /
   live_diameter`.
3. **Review:** activate either profile after reviewing its validity limits. Calibrated
   road values are marked `EST`; values using the manual depth control are marked
   `ASSUMED`.

The road profile is tied to the camera index, resolution scale, brightness threshold,
lamp, exposure behaviour, and viewing angle used during capture. It is intended only
for a controlled demonstration. A point light in one image does not contain general
absolute-range information, so use calibrated stereo or RGB-D sensing for defensible
physical distance measurements.

## Run from source

```bash
pip install -r requirements.txt
python run.py
```

Or as a Python module:

```bash
python -m glare_tracker
```

## Run the standalone executable

For a build made with the current script, double-click `dist/GlareTracker.exe` — no
Python is needed. The older local artifact is named `dist/GlareTracker-v1.exe` and does
not include the latest v1.2 changes.

## Build the executable

From the project root in PowerShell:

```powershell
./scripts/build_exe.ps1
```

The executable is created at `dist/GlareTracker.exe`. If Inno Setup (`iscc`) is available, an installer is also created at `installer-output/GlareTracker-Setup.exe`.

## Project structure

```
├── run.py                      # Launcher script (entry point)
├── glare_tracker/              # Main application package
│   ├── __init__.py             #   Package metadata & version
│   ├── __main__.py             #   python -m glare_tracker support
│   ├── app.py                  #   QApplication setup, main()
│   ├── config.py               #   TrackingConfig dataclass
│   ├── geometry.py             #   Intersection & coordinate math
│   ├── calibration.py          #   Calibration profiles and persistence
│   ├── operating_modes.py      #   Mode/state source policy
│   ├── styles.py               #   Centralized application theme stylesheet
│   ├── camera.py               #   Webcam capture thread (OpenCV + MediaPipe)
│   ├── capture.py              #   Compatible backend/profile camera setup
│   ├── tracking.py             #   TrackingController (business logic)
│   ├── window.py               #   MainWindow (layout + signal wiring)
│   └── widgets/                #   UI components
│       ├── __init__.py         #     Re-exports
│       ├── video.py            #     Camera feed display
│       ├── windshield_2d.py    #     2D windshield front view
│       ├── scene_3d.py         #     3D OpenGL visualization
│       ├── dashboard.py        #     Reusable dashboard and camera components
│       ├── icons.py            #     Dependency-free vector icon factory
│       ├── readout.py          #     Telemetry readout panel
│       ├── controls.py         #     User controls & inputs
│       └── calibration_wizard.py #   Guided distance calibration
├── tests/                      # Automated regression tests
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── assets/                     # Branding (icon files)
├── docs/                       # Indexed plans, guides, protocols, and references
├── scripts/                    # Build & utility scripts
└── dist/                       # Built executable (git-ignored)
```

The application needs a working webcam and Windows graphics support for the 3D view.
Default camera indices are 0 for the driver, 1 for the first outdoor camera, and 2
for the optional second stereo camera. Camera origins are modelled at the top-centre
of the windshield by default.
