# GlareTracker

GlareTracker is a Windows desktop application that tracks driver eye position from a webcam and visualizes glare intersections on a virtual windshield.

## Run from source

```bash
pip install -r requirements.txt
python glare_tracker.py
```

## Run the standalone executable

Double-click `dist/GlareTracker.exe` — no Python needed.

## Build the executable

From the project root in PowerShell:

```powershell
./scripts/build_exe.ps1
```

The executable is created at `dist/GlareTracker.exe`. The build includes version metadata for GlareTracker 1.0.0. If Inno Setup (`iscc`) is available, an installer is also created at `installer-output/GlareTracker-Setup.exe`.

## Project structure

```
├── glare_tracker.py        # Main application source code
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── assets/                 # Branding
│   ├── glaretracker-icon.ico
│   └── glaretracker-icon.svg
├── docs/                   # Documentation
│   ├── GlareTracker-Technical-Guide.html
│   └── GlareTracker-Technical-Guide.pdf
├── scripts/                # Build & utility scripts
│   ├── build_exe.ps1           # Build the .exe
│   ├── glare_tracker.spec      # PyInstaller config
│   ├── installer.iss           # Inno Setup installer config
│   ├── version_info.txt        # Windows version metadata
│   ├── generate_icon.py        # Regenerate .ico from code
│   └── CreateDesktopShortcut.ps1
└── dist/                   # Built output (git-ignored)
    └── GlareTracker.exe
```

The application needs a working webcam and Windows graphics support for the 3D view.