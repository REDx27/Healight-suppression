# GlareTracker

GlareTracker is a Windows desktop application that tracks driver eye position from a webcam and visualizes glare intersections on a virtual windshield.

## Run the application

For a packaged build, double-click `GlareTracker.exe` directly. Run `CreateDesktopShortcut.ps1` once to create both the project-root and Desktop shortcuts with the GlareTracker icon.

## Build the executable

From PowerShell:

```powershell
./build_exe.ps1
```

The executable is created at `dist/GlareTracker.exe` and copied to the project root as `GlareTracker.exe`. The build includes version metadata for `GlareTracker 1.0.0`.

## Build the installer

Install Inno Setup on Windows, ensure `iscc.exe` is available on `PATH`, and run:

```powershell
./build_exe.ps1
```

The installer is created at `installer-output/GlareTracker-Setup.exe`. It installs per-user, creates a Start Menu shortcut, and optionally creates a desktop shortcut.

The application needs a working webcam and Windows graphics support for the 3D view.

## Branding assets

The application icon is `assets/glaretracker-icon.ico`. Its editable vector source is `assets/glaretracker-icon.svg`. To regenerate the Windows icon after changing the design, run `python generate_icon.py`.