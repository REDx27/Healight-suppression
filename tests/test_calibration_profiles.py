"""Regression tests for guided single-camera demonstration calibration."""

from pathlib import Path

import cv2
import numpy as np

import glare_tracker.calibration as calibration_module
from glare_tracker.calibration import (
    DriverDepthCalibration,
    MonocularRangeCalibration,
    load_driver_depth_calibration,
    load_monocular_range_calibration,
    save_driver_depth_calibration,
    save_monocular_range_calibration,
)
from glare_tracker.headlight_detector import detect_bright_spot_observation


def test_driver_profile_builds_expected_intrinsic_scale():
    profile = DriverDepthCalibration(
        ipd_cm=6.4,
        reference_distance_cm=50.0,
        reference_ipd_px=64.0,
        focal_length_px=500.0,
        image_size=(640, 480),
        camera_index=0,
    )

    intrinsic = profile.as_intrinsic_calibration()

    assert intrinsic.focal_length_px == 500.0
    assert intrinsic.principal_point == (320.0, 240.0)
    assert np.allclose(intrinsic.dist_coeffs, 0.0)


def test_road_profile_uses_inverse_apparent_size():
    profile = MonocularRangeCalibration(
        reference_distance_cm=200.0,
        reference_diameter_px=20.0,
        range_scale_cm_px=4000.0,
        image_size=(640, 480),
        camera_index=1,
        brightness_threshold=205,
    )

    assert profile.estimate_distance_cm(20.0) == 200.0
    assert profile.estimate_distance_cm(10.0) == 400.0
    assert profile.estimate_distance_cm(40.0) == 100.0


def test_profiles_round_trip_with_camera_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(calibration_module, "_calibration_dir", lambda: Path(tmp_path))
    driver = DriverDepthCalibration(6.3, 55.0, 60.0, 523.8, (640, 480), 0)
    road = MonocularRangeCalibration(250.0, 18.0, 4500.0, (640, 480), 1, 215)

    save_driver_depth_calibration(driver)
    save_monocular_range_calibration(road)

    loaded_driver = load_driver_depth_calibration()
    loaded_road = load_monocular_range_calibration()
    assert loaded_driver == driver
    assert loaded_road == road


def test_bright_spot_observation_includes_apparent_diameter():
    frame = np.full((480, 640, 3), 70, dtype=np.uint8)
    cv2.circle(frame, (410, 205), 12, (230, 230, 230), -1)

    observation = detect_bright_spot_observation(frame)

    assert observation is not None
    assert abs(observation.center[0] - 410.0) < 2.0
    assert abs(observation.center[1] - 205.0) < 2.0
    assert observation.diameter_px > 5.0
