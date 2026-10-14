"""Unit coverage for camera-to-windshield rigid transforms."""

import json

import cv2
import numpy as np
import pytest

from glare_tracker.extrinsics import (
    CameraExtrinsicProfile,
    RigidTransform3D,
    build_extrinsic_profile,
    evaluate_transform,
    fit_rigid_transform,
    intrinsic_fingerprint,
    load_extrinsic_profile,
    project_pixel_to_windshield_plane,
    save_extrinsic_profile,
    solve_pnp_camera_to_windshield,
)


def _rotation_z(degrees):
    angle = np.deg2rad(degrees)
    return np.array(
        [
            [np.cos(angle), -np.sin(angle), 0.0],
            [np.sin(angle), np.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )


def _fingerprint():
    camera_matrix = np.array(
        [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]
    )
    return intrinsic_fingerprint(camera_matrix, np.zeros(5))


def test_identity_and_translation_transform_points():
    identity = RigidTransform3D.identity("camera")
    assert identity.apply((1.0, 2.0, 3.0)) == pytest.approx((1.0, 2.0, 3.0))

    translated = RigidTransform3D(
        np.eye(3), np.array([10.0, -4.0, 2.5]), "camera", "windshield"
    )
    assert translated.apply((1.0, 2.0, 3.0)) == pytest.approx(
        (11.0, -2.0, 5.5)
    )


def test_rotation_inverse_and_composition_round_trip():
    camera_to_mount = RigidTransform3D(
        _rotation_z(90), [1.0, 2.0, 3.0], "camera", "mount"
    )
    mount_to_windshield = RigidTransform3D(
        _rotation_z(-30), [-4.0, 5.0, 1.0], "mount", "windshield"
    )
    combined = camera_to_mount.then(mount_to_windshield)
    point = (3.0, -2.0, 7.0)

    sequential = mount_to_windshield.apply(camera_to_mount.apply(point))
    assert combined.apply(point) == pytest.approx(sequential)
    assert combined.inverse().apply(combined.apply(point)) == pytest.approx(point)

    with pytest.raises(ValueError, match="Cannot compose"):
        mount_to_windshield.then(camera_to_mount)


@pytest.mark.parametrize(
    ("rotation", "translation", "message"),
    [
        (np.eye(2), np.zeros(3), "shape"),
        (np.diag([2.0, 1.0, 1.0]), np.zeros(3), "orthonormal"),
        (np.diag([-1.0, 1.0, 1.0]), np.zeros(3), "determinant"),
        (np.eye(3), np.zeros(2), "three coordinates"),
        (np.eye(3), [0.0, np.nan, 0.0], "non-finite"),
    ],
)
def test_invalid_rigid_transforms_are_rejected(rotation, translation, message):
    with pytest.raises(ValueError, match=message):
        RigidTransform3D(rotation, translation)


def test_kabsch_fit_recovers_known_camera_pose():
    source = np.array(
        [
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [0.0, 20.0, 0.0],
            [0.0, 0.0, 30.0],
            [5.0, 7.0, 11.0],
        ]
    )
    expected = RigidTransform3D(
        _rotation_z(25), [12.0, -8.0, 19.5], "camera", "windshield"
    )
    target = expected.apply(source)

    fitted = fit_rigid_transform(source, target)
    metrics = evaluate_transform(fitted, source, target)

    assert fitted.rotation == pytest.approx(expected.rotation, abs=1e-10)
    assert fitted.translation_cm == pytest.approx(
        expected.translation_cm, abs=1e-10
    )
    assert metrics.point_count == 5
    assert metrics.rmse_cm < 1e-10
    assert metrics.max_error_cm < 1e-10


def test_kabsch_fit_rejects_insufficient_and_collinear_points():
    with pytest.raises(ValueError, match="At least three"):
        fit_rigid_transform([[0, 0, 0], [1, 0, 0]], [[0, 0, 0], [1, 0, 0]])
    with pytest.raises(ValueError, match="must not be collinear"):
        fit_rigid_transform(
            [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
            [[0, 1, 0], [1, 1, 0], [2, 1, 0]],
        )


def test_solve_pnp_recovers_installed_camera_to_windshield_pose():
    camera_to_windshield = RigidTransform3D(
        np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, -1.0, 0.0],
            ]
        ),
        [0.0, -50.0, 10.0],
        "driver_camera",
        "windshield",
    )
    windshield_points = np.array(
        [
            [-20.0, 0.0, 0.0],
            [20.0, 0.0, 0.0],
            [-20.0, 0.0, 20.0],
            [20.0, 0.0, 20.0],
            [0.0, 0.0, 5.0],
            [0.0, 0.0, 15.0],
        ]
    )
    windshield_to_camera = camera_to_windshield.inverse()
    rotation_vector, _ = cv2.Rodrigues(windshield_to_camera.rotation)
    camera_matrix = np.array(
        [[800.0, 0.0, 320.0], [0.0, 800.0, 240.0], [0.0, 0.0, 1.0]]
    )
    distortion = np.zeros(5)
    image_points, _ = cv2.projectPoints(
        windshield_points,
        rotation_vector,
        windshield_to_camera.translation_cm,
        camera_matrix,
        distortion,
    )

    result = solve_pnp_camera_to_windshield(
        windshield_points,
        image_points.reshape(-1, 2),
        camera_matrix,
        distortion,
        camera_frame="driver_camera",
    )

    assert result.transform.rotation == pytest.approx(
        camera_to_windshield.rotation, abs=1e-6
    )
    assert result.transform.translation_cm == pytest.approx(
        camera_to_windshield.translation_cm, abs=1e-6
    )
    assert result.reprojection_metrics.rmse_px < 1e-5
    assert result.reprojection_metrics.max_error_px < 1e-5
    for image_point, expected_point in zip(
        image_points.reshape(-1, 2), windshield_points
    ):
        recovered = project_pixel_to_windshield_plane(
            image_point,
            camera_matrix,
            distortion,
            result.transform,
        )
        assert recovered == pytest.approx(expected_point, abs=1e-6)


def test_profile_round_trip_and_compatibility_checks(tmp_path):
    source = np.array(
        [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], dtype=float
    )
    expected = RigidTransform3D(
        _rotation_z(12), [2.0, -1.0, 19.5], "road_camera", "windshield"
    )
    target = expected.apply(source)
    fingerprint = _fingerprint()
    profile = build_extrinsic_profile(
        source,
        target,
        camera_index=1,
        image_size=(640, 480),
        device_id="usb-camera-serial-123",
        mount_id="road-rig-v1",
        intrinsic_fingerprint=fingerprint,
        from_frame="road_camera",
    )
    path = save_extrinsic_profile(profile, tmp_path / "road_extrinsic.json")
    loaded = load_extrinsic_profile(path)

    assert loaded.camera_index == 1
    assert loaded.transform.rotation == pytest.approx(profile.transform.rotation)
    assert loaded.transform.translation_cm == pytest.approx(
        profile.transform.translation_cm
    )
    assert loaded.compatibility_errors(
        camera_index=1,
        image_size=(640, 480),
        device_id="usb-camera-serial-123",
        mount_id="road-rig-v1",
        intrinsic_fingerprint=fingerprint,
    ) == ()
    assert loaded.compatibility_errors(
        camera_index=2,
        image_size=(1280, 720),
        device_id="another-device",
        mount_id="moved-mount",
        intrinsic_fingerprint="0" * 64,
    ) == (
        "camera index changed",
        "image size changed",
        "camera device changed",
        "camera mount changed",
        "intrinsic calibration changed",
    )


def test_profile_loader_rejects_unknown_version(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"profile_version": 99}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_extrinsic_profile(path)
