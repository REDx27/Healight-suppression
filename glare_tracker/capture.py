"""Cross-camera OpenCV capture helpers.

Cheap USB webcams vary widely in backend, codec, resolution, and control
support.  These helpers keep capture setup conservative and provide fallbacks
without making the tracking workers depend on one Windows driver stack.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import cv2
from PyQt5.QtCore import QThread, pyqtSignal


@dataclass(frozen=True)
class CameraDevice:
    """One OpenCV camera index confirmed by a successful frame read."""

    index: int
    width: int
    height: int
    backend: str


class CameraDiscoveryThread(QThread):
    """Probe camera indices without freezing the operator interface."""

    cameras_discovered = pyqtSignal(object)

    def __init__(self, max_index: int = 10, parent=None):
        super().__init__(parent)
        self.max_index = max(1, int(max_index))

    def run(self):
        devices = []
        for camera_index in range(self.max_index):
            if self.isInterruptionRequested():
                break
            capture, backend_name = open_video_capture(camera_index)
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
                ))
            finally:
                try:
                    capture.release()
                except cv2.error:
                    pass
        self.cameras_discovered.emit(devices)


def open_video_capture(camera_index: int):
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
            return capture, backend_name
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
