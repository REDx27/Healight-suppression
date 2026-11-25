"""Exercise the actual native driver-processing branch with deterministic inputs."""

from types import SimpleNamespace
import time

import cv2
import numpy as np
import pytest

import glare_tracker.camera as camera_module
from glare_tracker.calibration import CalibrationResult
from glare_tracker.config import TrackingConfig
from glare_tracker.extrinsics import RigidTransform3D
from glare_tracker.installation import camera_record, frontal_pose


def model():
    return CalibrationResult(np.array([[600., 0, 320], [0, 600., 240], [0, 0, 1]]),
                             np.zeros(5), (640, 480), .2)


@pytest.mark.parametrize("sensor_valid, frame_size, accepted", [
    (True, (640, 480), True), (False, (640, 480), False), (True, (320, 240), False),
])
def test_native_frame_to_installed_eyes_requires_live_valid_range(monkeypatch, sensor_valid, frame_size, accepted):
    worker = camera_module.VideoCaptureThread(0)
    pose = RigidTransform3D(np.array([[-1., 0, 0], [0, 0, -1], [0, -1, 0]]),
                            [0., 0., 28.], "driver", "windshield")
    worker.update_config(TrackingConfig(
        driver_model=camera_record(model(), 0), installed_pose={"transform": pose.to_dict()},
        live_driver_distance=True,
        tof_profile={"device_id": "tof-1", "maximum_pose_deg": 10., "bias_cm": 1.2,
                     "min_cm": 30., "max_cm": 70., "sensor_z_cm": .5, "eye_offset_cm": .2},
        generation=7))
    worker.sensor_service = SimpleNamespace(history=[{
        "device_id": "tof-1", "valid": sensor_valid, "raw_cm": 48.8,
        "observed_ns": time.monotonic_ns() - 5_000_000, "uncertainty_ns": 1_000_000}])
    landmarks = [SimpleNamespace(x=.5, y=.5, z=0.) for _ in range(478)]
    landmarks[468].x, landmarks[473].x = .45, .55
    face = SimpleNamespace(process=lambda frame: SimpleNamespace(
        multi_face_landmarks=[SimpleNamespace(landmark=landmarks)]), close=lambda: None)

    class Capture:
        reads = 0

        def read(self):
            self.reads += 1
            if self.reads > 1:
                worker._running = False
                return False, None
            return True, np.zeros((frame_size[1], frame_size[0], 3), np.uint8)

        def release(self):
            self.released = True

    capture = Capture()
    monkeypatch.setattr(camera_module, "open_video_capture", lambda index: (capture, "mock"))
    monkeypatch.setattr(camera_module, "configure_video_capture", lambda cap: (640, 480, 30))
    monkeypatch.setattr(worker, "_create_face_tracker", lambda: (face, False))
    monkeypatch.setattr(worker, "_estimate_head_pose", lambda *args: (180., 0., 0., [0, 0, 50]))
    observations = []
    worker.eye_observation.connect(observations.append)
    worker.run()
    assert capture.released and len(observations) == 1
    result = observations[0]
    assert result["valid"] is accepted and result["generation"] == 7
    if accepted:
        # Native x=.45 remains on camera-left before the installed driver's
        # orientation changes its sign. A premature preview mirror fails this.
        np.testing.assert_allclose(result["eyes"][0], [32 / 600 * 50.7, -50.7, 28.])
        np.testing.assert_allclose(result["eyes"][1], [-32 / 600 * 50.7, -50.7, 28.])
        assert result["frame"] == "lcd" and result["range_observed_ns"] is not None
    else:
        assert result["eyes"] is None  # No silent IPD fallback on failed ToF.


def test_actual_face_model_pnp_accepts_a_frontal_head():
    camera = model()
    pixels, _ = cv2.projectPoints(camera_module._HEAD_MODEL_POINTS_CM,
                                  np.array([np.pi, 0., 0.]), np.array([0., 0., 50.]),
                                  camera.camera_matrix, camera.dist_coeffs)
    landmarks = [SimpleNamespace(x=.5, y=.5) for _ in range(478)]
    for index, pixel in zip(camera_module._HEAD_LANDMARK_INDICES, pixels.reshape(-1, 2)):
        landmarks[index] = SimpleNamespace(x=pixel[0] / 640, y=pixel[1] / 480)
    worker = camera_module.VideoCaptureThread(0)
    pose = worker._estimate_head_pose(landmarks, 640, 480, camera.camera_matrix, camera.dist_coeffs)
    assert pose is not None and frontal_pose(pose[0], pose[1])


@pytest.mark.parametrize("path", ["native", "legacy", "preview"])
@pytest.mark.parametrize("live", [False, True])
def test_fixed_distance_stays_constant_while_eye_tracking_moves(monkeypatch, path, live):
    worker = camera_module.VideoCaptureThread(0)
    worker.update_config(TrackingConfig(
        eye_dist_cm=75., live_driver_distance=live,
        driver_model=camera_record(model(), 0) if path == "native" else None,
        use_calibration=path == "legacy"))
    if path == "legacy":
        worker.set_calibration(model())
    calls = []

    def face_process(frame):
        landmarks = [SimpleNamespace(x=.5, y=.5, z=0.) for _ in range(478)]
        landmarks[468].x, landmarks[473].x = .45 + .01 * len(calls), .55
        calls.append(True)
        return SimpleNamespace(multi_face_landmarks=[SimpleNamespace(landmark=landmarks)])

    class Capture:
        reads = 0

        def read(self):
            self.reads += 1
            if self.reads > 2:
                worker._running = False
                return False, None
            return True, np.zeros((480, 640, 3), np.uint8)

        def release(self):
            pass

    monkeypatch.setattr(camera_module, "open_video_capture", lambda index: (Capture(), "mock"))
    monkeypatch.setattr(camera_module, "configure_video_capture", lambda cap: (640, 480, 30))
    monkeypatch.setattr(worker, "_create_face_tracker", lambda: (
        SimpleNamespace(process=face_process, close=lambda: None), False))
    if live:
        monkeypatch.setattr(worker, "_estimate_head_pose", lambda *args: (180., 0., 0., [0, 0, 50]))
    else:
        def forbidden_estimate(*args):
            raise AssertionError("Distance estimation must not run when disabled")
        monkeypatch.setattr(worker, "_estimate_head_pose", forbidden_estimate)
        monkeypatch.setattr(camera_module, "estimate_ipd_depth", forbidden_estimate)
    observations = []
    worker.eye_observation.connect(observations.append)
    worker.run()
    assert len(observations) == len(calls) == 2
    assert all(s["valid"] for s in observations)
    if not live or path == "preview":
        assert [s["eye_depth_cm"] for s in observations] == [75., 75.]
        assert all(s["depth_source"] == "Fixed/reference distance" for s in observations)
        assert all(eye[1] == -75. for s in observations for eye in s["eyes"])
    else:
        assert observations[0]["eye_depth_cm"] != observations[1]["eye_depth_cm"]
        assert all(s["depth_source"].startswith("IPD") for s in observations)
    assert observations[0]["eyes"][0][0] != observations[1]["eyes"][0][0]
