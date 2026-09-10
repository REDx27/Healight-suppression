from PyInstaller.utils.hooks import collect_all


datas = []
binaries = []
hiddenimports = []

for package in ("mediapipe", "pyqtgraph"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

datas.append(("assets/glaretracker-icon.ico", "assets"))


analysis = Analysis(
    ["glare_tracker.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="GlareTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/glaretracker-icon.ico",
    version="version_info.txt",
    disable_windowed_traceback=False,
)