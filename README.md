# GlareTracker

GlareTracker is a Windows desktop application that tracks driver eye position from a webcam and visualizes glare intersections on a virtual windshield.

Headlight coordinates can be supplied manually or detected from cameras. Auto mode
supports an initial single-camera setup (with a user-supplied depth estimate) and a
calibrated or fallback stereo-camera setup. The driver and outdoor camera feeds are
shown in the sidebar, together with connection and detection status.

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

Double-click `dist/GlareTracker.exe` — no Python needed.

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
│   ├── styles.py               #   Dark theme stylesheet
│   ├── camera.py               #   Webcam capture thread (OpenCV + MediaPipe)
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
│       └── controls.py        #     User controls & inputs
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── assets/                     # Branding (icon files)
├── docs/                       # Technical documentation
├── scripts/                    # Build & utility scripts
└── dist/                       # Built executable (git-ignored)
```

The application needs a working webcam and Windows graphics support for the 3D view.
Default camera indices are 0 for the driver, 1 for the first outdoor camera, and 2
for the optional second stereo camera. Camera origins are modelled at the top-centre
of the windshield by default.
