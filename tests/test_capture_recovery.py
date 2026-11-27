"""Camera startup cancellation and recovery from an unusable landmark frame."""

from types import SimpleNamespace
from threading import Event

import cv2
import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

import glare_tracker.camera as driver
import glare_tracker.headlight_detector as road
from glare_tracker.config import TrackingConfig


@pytest.mark.parametrize("module,factory", [
    (driver, driver.VideoCaptureThread),
    (road, road.MonocularHeadlightDetectorThread),
    (road, road.HeadlightDetectorThread),
])
def test_stop_during_startup_is_not_overwritten_by_run(monkeypatch, module, factory):
    app = QApplication.instance() or QApplication([])
    entered, release = Event(), Event()
    class StartupBlocked(factory):
        def run(self):
            entered.set()
            release.wait(3.)
            super().run()
    worker = StartupBlocked()
    opens = []
    def unexpected_open(index):
        opens.append(index)
        return None, "mock"
    monkeypatch.setattr(module, "open_video_capture", unexpected_open)
    wait = worker.wait
    def release_then_wait(timeout):
        release.set()
        return wait(timeout)
    monkeypatch.setattr(worker, "wait", release_then_wait)
    # Actual QThread is running, but the capture run() has not initialized yet.
    worker.start()
    try:
        assert entered.wait(2.)
        worker.stop()
        assert not worker.isRunning() and not worker._running and not opens
    finally:
        release.set()
        wait(5000)
    app.processEvents()


@pytest.mark.parametrize("bad_frame", ["missing iris", "nan", "outside image"])
def test_bad_iris_frame_is_rejected_then_next_frame_tracks(monkeypatch, bad_frame):
    app = QApplication.instance() or QApplication([])
    worker = driver.VideoCaptureThread()
    worker.update_config(TrackingConfig(live_driver_distance=False))
    valid = [SimpleNamespace(x=.5, y=.5, z=0.) for _ in range(478)]
    valid[468].x, valid[473].x = .45, .55
    bad = [SimpleNamespace(x=p.x, y=p.y, z=p.z) for p in valid]
    if bad_frame == "missing iris":
        bad = bad[:468]
    else:
        bad[468].x = float("nan") if bad_frame == "nan" else 1.5
    faces = iter([bad, valid])
    face = SimpleNamespace(process=lambda frame: SimpleNamespace(
        multi_face_landmarks=[SimpleNamespace(landmark=next(faces))]), close=lambda: None)

    class Capture:
        reads = 0
        released = False
        def read(self):
            self.reads += 1
            if self.reads > 2:
                worker._running = False
                return False, None
            return True, np.zeros((480, 640, 3), np.uint8)
        def release(self):
            self.released = True

    cap = Capture()
    monkeypatch.setattr(driver, "open_video_capture", lambda index: (cap, "mock"))
    monkeypatch.setattr(driver, "configure_video_capture", lambda cap: (640, 480, 30))
    monkeypatch.setattr(worker, "_create_face_tracker", lambda: (face, False))
    observations, timing, previews, status = [], [], [], []
    worker.eye_observation.connect(observations.append)
    worker.pipeline_timing.connect(timing.append)
    worker.frame_ready.connect(previews.append)
    worker.camera_status.connect(lambda message, connected: status.append(message))
    worker.run()
    assert cap.released and cap.reads == 3
    assert len(previews) == 2 and len(observations) == 1 and observations[0]["valid"]
    assert [t["observation_valid"] for t in timing] == [False, True]
    assert not any("error" in message.lower() for message in status)
    app.processEvents()


def test_unusable_head_pose_does_not_raise_or_produce_depth(monkeypatch):
    app = QApplication.instance() or QApplication([])
    worker = driver.VideoCaptureThread()
    landmarks = [SimpleNamespace(x=.5, y=.5) for _ in range(478)]
    landmarks[1].x = float("nan")
    assert worker._estimate_head_pose(landmarks, 640, 480, np.eye(3), np.zeros(5)) is None
    landmarks[1].x = .5
    def failed_pnp(*args, **kwargs):
        raise cv2.error("degenerate pose")
    monkeypatch.setattr(driver.cv2, "solvePnP", failed_pnp)
    assert worker._estimate_head_pose(landmarks, 640, 480, np.eye(3), np.zeros(5)) is None
    app.processEvents()
