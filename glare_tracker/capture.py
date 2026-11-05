"""Cross-camera OpenCV capture helpers.

Cheap USB webcams vary widely in backend, codec, resolution, and control
support.  These helpers keep capture setup conservative and provide fallbacks
without making the tracking workers depend on one Windows driver stack.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
import re
import subprocess

import cv2
from PyQt5.QtCore import QThread, pyqtSignal


# Conservative shared mode for the identical external road-camera pair.
# The previous temporary 320x240 profile is no longer used. Calibration and
# live stereo must use the same resolution; 15 FPS keeps three-camera USB
# bandwidth conservative while retaining full VGA calibration detail.
ROAD_STEREO_WIDTH = 640
ROAD_STEREO_HEIGHT = 480
ROAD_STEREO_FPS = 15


@dataclass(frozen=True)
class CameraDevice:
    """One OpenCV camera index confirmed by a successful frame read."""

    index: int
    width: int
    height: int
    backend: str
    name: str = ""


def parse_directshow_camera_names(output: str) -> list[str]:
    """Return DirectShow video-device names in enumeration order."""

    return re.findall(r'\]\s+"([^"]+)"\s+\(video\)', output or "")


def directshow_camera_names(timeout_seconds: float = 5.0) -> list[str]:
    """Best-effort Windows names matching OpenCV CAP_DSHOW index order."""

    if not sys.platform.startswith("win"):
        return []
    try:
        completed = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-list_devices", "true",
                "-f", "dshow", "-i", "dummy",
            ],
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout_seconds)),
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_directshow_camera_names(
        f"{completed.stdout or ''}\n{completed.stderr or ''}")


class CameraDiscoveryThread(QThread):
    """Probe camera indices without freezing the operator interface."""

    cameras_discovered = pyqtSignal(object)

    def __init__(self, max_index: int = 10, parent=None):
        super().__init__(parent)
        self.max_index = max(1, int(max_index))

    def run(self):
        devices = []
        names = directshow_camera_names()
        for camera_index in range(self.max_index):
            if self.isInterruptionRequested():
                break
            capture, backend_name = open_video_capture(camera_index, verify_frames=True)
            if capture is None:
                continue
            try:
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                height, width = frame.shape[:2]
                devices.append(CameraDevice(
                    index=camera_index,
                    width=int(width),
                    height=int(height),
                    backend=backend_name,
                    name=(names[camera_index]
                          if camera_index < len(names) else ""),
                ))
            finally:
                try:
                    capture.release()
                except cv2.error:
                    pass
        self.cameras_discovered.emit(devices)


def open_video_capture(camera_index: int, verify_frames: bool = False):
    """Open a camera using the first working backend.

    DirectShow is normally the most predictable option on Windows, but some
    low-cost UVC devices work only through Media Foundation or OpenCV's
    automatic backend selection.
    """
    backends = []
    if sys.platform.startswith("win"):
        backends.extend([
            ("DirectShow", cv2.CAP_DSHOW),
            ("Media Foundation", cv2.CAP_MSMF),
        ])
    backends.append(("Automatic", None))

    for backend_name, backend in backends:
        capture = (cv2.VideoCapture(camera_index) if backend is None
                   else cv2.VideoCapture(camera_index, backend))
        if capture.isOpened():
            if not verify_frames:
                return capture, backend_name
            # UVC/DirectShow can report opened before the stream is ready, or
            # return a dead handle. Require a frame before accepting a backend.
            for _ in range(10):
                ok, frame = capture.read()
                if ok and frame is not None and frame.size:
                    return capture, backend_name
                QThread.msleep(50)
        try:
            capture.release()
        except cv2.error:
            pass
    return None, "Unavailable"


def configure_video_capture(
    capture,
    width: int = 640,
    height: int = 480,
    fps: int = 30,
    prefer_mjpeg: bool = True,
) -> tuple[int, int, float]:
    """Request a broadly supported low-latency camera profile.

    Unsupported properties are intentionally non-fatal; OpenCV retains the
    nearest mode offered by the device.  The returned values are the actual
    negotiated width, height, and reported FPS.
    """
    if prefer_mjpeg:
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_FPS, fps)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or width
    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or height
    actual_fps = float(capture.get(cv2.CAP_PROP_FPS)) or float(fps)
    return actual_width, actual_height, actual_fps


def configure_road_stereo_capture(capture) -> tuple[int, int, float]:
    """Apply the measured low-bandwidth profile shared by both road cameras."""
    return configure_video_capture(
        capture,
        width=ROAD_STEREO_WIDTH,
        height=ROAD_STEREO_HEIGHT,
        fps=ROAD_STEREO_FPS,
    )
