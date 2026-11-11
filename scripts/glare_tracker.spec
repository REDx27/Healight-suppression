from PyInstaller.utils.hooks import collect_all


datas = []
binaries = []
hiddenimports = []

# The application uses MediaPipe face landmarks and PyQtGraph's OpenGL scene.
# Their distributions also ship conversion tools, benchmarks, tests, Jupyter
# integrations, and a large example gallery.  Excluding those trees avoids
# pulling pytest, Matplotlib, JAX/Torch probes, and unrelated demo assets into
# the one-file release.
excluded_submodule_prefixes = {
    "mediapipe": (
        "mediapipe.tasks.python.benchmark",
        "mediapipe.tasks.python.metadata",
        "mediapipe.tasks.python.test",
    ),
    "pyqtgraph": (
        "pyqtgraph.examples",
        "pyqtgraph.jupyter",
        "pyqtgraph.tests",
    ),
}


def release_submodule(module_name, package_name):
    if (
        package_name == "mediapipe"
        and module_name.startswith("mediapipe.tasks.python.genai.")
    ):
        return False
    return not module_name.startswith(excluded_submodule_prefixes[package_name])


for package in ("mediapipe", "pyqtgraph"):
    package_datas, package_binaries, package_hiddenimports = collect_all(
        package,
        filter_submodules=lambda module_name, name=package:
            release_submodule(module_name, name),
        exclude_datas=["**/test/**", "**/tests/**", "**/examples/**"],
    )
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

datas.append(("../assets/glaretracker-icon.ico", "assets"))
datas.append(("../assets/face_landmarker.task", "assets"))
datas.append(("../assets/calibration", "assets/calibration"))
datas.append((
    "../output/pdf/road_stereo_chessboard_A4_9x6_20mm.pdf",
    "output/pdf",
))


analysis = Analysis(
    ["../run.py"],
    pathex=[".."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "pyqtgraph.examples",
        "pyqtgraph.jupyter",
        "mediapipe.tasks.python.benchmark",
        "mediapipe.tasks.python.genai.bundler",
        "mediapipe.tasks.python.genai.converter",
        "mediapipe.tasks.python.metadata",
        "mediapipe.tasks.python.test",
    ],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="GlareTracker-v1.3",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="../assets/glaretracker-icon.ico",
    version="version_info.txt",
    disable_windowed_traceback=False,
)
