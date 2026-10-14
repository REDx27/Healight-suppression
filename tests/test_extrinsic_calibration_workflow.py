"""End-to-end tests for the guarded extrinsic-calibration CLI workflow."""

import json

import cv2
import numpy as np
import pytest

from glare_tracker.extrinsics import RigidTransform3D, load_extrinsic_profile
from scripts.calibrate_extrinsics import calibrate_from_file


def _input_data():
    camera_to_windshield = RigidTransform3D(
        np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, -1.0, 0.0],
            ]
        ),
        [1.0, -55.0, 12.0],
        "road_camera",
        "windshield",
    )
    camera_matrix = np.array(
        [[900.0, 0.0, 320.0], [0.0, 900.0, 240.0], [0.0, 0.0, 1.0]]
    )
    distortion = np.zeros(5)
    points = np.array(
        [
            [-20.0, 0.0, 0.0],
            [20.0, 0.0, 0.0],
            [-20.0, 0.0, 20.0],
            [20.0, 0.0, 20.0],
            [-10.0, 0.0, 5.0],
            [10.0, 0.0, 15.0],
            [-15.0, 0.0, 10.0],
            [15.0, 0.0, 10.0],
            [0.0, 0.0, 2.0],
            [0.0, 0.0, 18.0],
            [-5.0, 0.0, 12.0],
        ]
    )
    inverse = camera_to_windshield.inverse()
    rotation_vector, _ = cv2.Rodrigues(inverse.rotation)
    image_points, _ = cv2.projectPoints(
        points,
        rotation_vector,
        inverse.translation_cm,
        camera_matrix,
        distortion,
    )
    image_points = image_points.reshape(-1, 2)

    def targets(start, end, prefix):
        return [
            {
                "id": f"{prefix}{index + 1}",
                "windshield_cm": points[index].tolist(),
                "image_px": image_points[index].tolist(),
            }
            for index in range(start, end)
        ]

    return {
        "camera": {
            "camera_index": 1,
            "image_size": [640, 480],
            "device_id": "usb-road-camera-123",
            "mount_id": "rigid-road-mount-v1",
            "frame_name": "road_camera",
        },
        "intrinsics": {
            "camera_matrix": camera_matrix.tolist(),
            "distortion": distortion.tolist(),
        },
        "acceptance": {
            "max_reprojection_rmse_px": 0.01,
            "max_validation_rmse_cm": 0.01,
            "max_validation_error_cm": 0.02,
        },
        "fit_targets": targets(0, 6, "FIT"),
        "validation_targets": targets(6, 11, "VAL"),
    }


def test_calibration_writes_profile_only_after_independent_validation_passes(
    tmp_path,
):
    input_path = tmp_path / "input.json"
    profile_path = tmp_path / "profile.json"
    report_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(_input_data()), encoding="utf-8")

    report = calibrate_from_file(input_path, profile_path, report_path)

    assert report["status"] == "PASS"
    assert report["checks"] == {
        "reprojection_rmse_px": True,
        "validation_rmse_cm": True,
        "validation_max_error_cm": True,
    }
    assert profile_path.exists()
    assert report_path.exists()
    profile = load_extrinsic_profile(profile_path)
    assert profile.fit_method == "solve_pnp"
    assert profile.reprojection_metrics.rmse_px < 0.01
    assert profile.fit_metrics.max_error_cm < 0.02


def test_failed_calibration_keeps_report_but_does_not_write_profile(tmp_path):
    data = _input_data()
    data["validation_targets"][0]["image_px"][0] += 25.0
    input_path = tmp_path / "input.json"
    profile_path = tmp_path / "profile.json"
    report_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")

    report = calibrate_from_file(input_path, profile_path, report_path)

    assert report["status"] == "FAIL"
    assert report["profile_written"] is False
    assert report_path.exists()
    assert not profile_path.exists()


def test_calibration_requires_predeclared_acceptance_limits(tmp_path):
    data = _input_data()
    del data["acceptance"]["max_validation_error_cm"]
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="must be declared before"):
        calibrate_from_file(
            input_path, tmp_path / "profile.json", tmp_path / "report.json"
        )
