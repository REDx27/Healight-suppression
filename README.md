# GlareTracker

GlareTracker is a Windows desktop application that tracks driver eye position from a webcam and visualizes glare intersections on a virtual windshield.

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