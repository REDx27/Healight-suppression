# GlareTracker

GlareTracker is a Windows desktop application that tracks driver eye position from a webcam and visualizes glare intersections on a virtual windshield.

## Run the application

For a packaged build, double-click `dist/GlareTracker.exe` or `Launch_GlareTracker.bat`.

## Build the executable

From PowerShell:

```powershell
./build_exe.ps1
```

The executable is created at `dist/GlareTracker.exe`. The build includes version metadata for `GlareTracker 1.0.0`.

## Build the installer

Install Inno Setup on Windows, ensure `iscc.exe` is available on `PATH`, and run:

```powershell
./build_exe.ps1
```

The installer is created at `installer-output/GlareTracker-Setup.exe`. It installs per-user, creates a Start Menu shortcut, and optionally creates a desktop shortcut.

The application needs a working webcam and Windows graphics support for the 3D view.