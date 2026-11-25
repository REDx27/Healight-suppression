"""Independent synthetic checks of measured camera/LCD and sensor geometry."""

import copy
import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from glare_tracker.calibration import CalibrationResult
from glare_tracker.extrinsics import RigidTransform3D
from glare_tracker.installation import (
    CalibrationStore, board_points, camera_model, camera_record, fit_installed_pose,
    fit_panel_mapping, fit_tof, frontal_pose, rig_compatibility_errors,
    triangulate_lcd, unproject_eye, validate_tof_profile,
)


def lens():
    return CalibrationResult(np.array([[600., 0, 320], [0, 610, 240], [0, 0, 1]]),
                             np.zeros(5), (640, 480), .2)


def pose_samples(side="road"):
    rotation = np.array([[1., 0, 0], [0, 0, 1], [0, -1, 0]])
    if side == "driver":
        rotation = np.diag([-1., -1., 1.]) @ rotation
    tilt, _ = cv2.Rodrigues(np.array([.015, -.025, .01]))
    transform = RigidTransform3D(tilt @ rotation, [2., 0., 28.], side, "windshield")
    inverse = transform.inverse()
    rvec, _ = cv2.Rodrigues(inverse.rotation)
    samples = []
    for i, (x, distance, z) in enumerate([
        (-10, 60, 22), (-7, 90, 24), (-12, 130, 26),
        (1, 60, 25), (-16, 90, 20), (-5, 130, 22),
        (-9, 75, 23), (-6, 105, 25), (-11, 115, 21),
    ]):
        origin = [x if side == "road" else -x, distance if side == "road" else -distance, z]
        points = board_points((9, 6), 2., origin, [0, 0, 0], side)
        pixels, _ = cv2.projectPoints(points, rvec, inverse.translation_cm,
                                      lens().camera_matrix, lens().dist_coeffs)
        samples.append({"points_cm": points.tolist(), "pixels": pixels.reshape(-1, 2).tolist(),
                        "pose_key": origin + [0, 0, 0], "split": "fit" if i < 6 else "validation"})
    return transform, samples


@pytest.mark.parametrize("side", ["road", "driver"])
def test_measured_board_poses_recover_native_camera_to_lcd(side):
    truth, samples = pose_samples(side)
    result = fit_installed_pose(samples, lens(), side)
    fitted = RigidTransform3D.from_dict(result["transform"])
    np.testing.assert_allclose(fitted.rotation, truth.rotation, atol=1e-6)
    np.testing.assert_allclose(fitted.translation_cm, truth.translation_cm, atol=1e-5)
    assert result["report"]["held_out_max_transverse_cm"] < 1e-5


def test_bad_held_out_pose_does_not_become_a_fit_sample():
    _, samples = pose_samples()
    for point in samples[-1]["pixels"]:
        point[0] += 12
    with pytest.raises(ValueError, match="held-out"):
        fit_installed_pose(samples, lens(), "road")
    _, samples = pose_samples()
    samples[-1]["pose_key"] = samples[0]["pose_key"]
    with pytest.raises(ValueError, match="different measured placements"):
        fit_installed_pose(samples, lens(), "road")


def test_pose_fit_requires_depth_diversity():
    _, samples = pose_samples()
    for sample in samples[:6]:
        sample["pose_key"][1] = 70
    with pytest.raises(ValueError, match="three measured Y"):
        fit_installed_pose(samples, lens(), "road")


def panel_samples():
    targets = ((.1, .1), (.9, .1), (.1, .9), (.9, .9), (.5, .1), (.5, .9),
               (.1, .5), (.5, .5), (.9, .5))
    return [{"uv": list(uv), "xz_cm": [40 * uv[0] - 20 + .05, 25 * (1 - uv[1]) - .03],
             "split": "fit" if i < 6 else "validation"} for i, uv in enumerate(targets)]


def test_panel_mapping_uses_measured_offsets_and_checks_separate_marks():
    result = fit_panel_mapping(panel_samples(), 40, 25)
    np.testing.assert_allclose(np.array(result["xz_to_uv"]) @ [.05, 12.47, 1], [.5, .5])
    samples = panel_samples()
    samples[-1]["xz_cm"][1] += 1
    with pytest.raises(ValueError, match="Held-out LCD"):
        fit_panel_mapping(samples, 40, 25)
    with pytest.raises(ValueError, match="dimensions/orientation"):
        fit_panel_mapping(panel_samples(), 34.5, 19.5)


def test_stereo_triangulation_undoes_rectification_before_installed_transform():
    model = lens()
    rotation, _ = cv2.Rodrigues(np.array([.01, -.03, .005]))
    translation = np.array([-15., .2, -.1])
    r1, r2, p1, p2, *_ = cv2.stereoRectify(
        model.camera_matrix, model.dist_coeffs, model.camera_matrix, model.dist_coeffs,
        model.image_size, rotation, translation.reshape(3, 1), flags=cv2.CALIB_ZERO_DISPARITY)
    stereo = SimpleNamespace(R=rotation, T=translation, R1=r1, P1=p1, P2=p2)
    raw = np.array([6., -4., 180.])
    rectified = r1 @ raw
    h = np.r_[rectified, 1.]
    left, right = p1 @ h, p2 @ h
    transform = RigidTransform3D(np.array([[1., 0, 0], [0, 0, 1], [0, -1, 0]]),
                                 [-7., 1., 28.], "road", "windshield")
    actual = triangulate_lcd(left[:2] / left[2], right[:2] / right[2], stereo,
                             {"transform": transform.to_dict()})
    np.testing.assert_allclose(actual, transform.apply(raw), atol=1e-8)


def test_native_eye_unprojection_retains_pixel_axis_signs():
    result = unproject_eye((380, 301), 50., lens())
    np.testing.assert_allclose(result, [5, 5, 50])
    record = camera_record(lens(), 0)
    assert camera_model(record).image_size == (640, 480)
    record["pixel_convention"] = "mirrored"
    with pytest.raises(ValueError, match="pixel convention"):
        camera_model(record)


def range_samples():
    return [{"reference_cm": distance, "raw_cm": [distance - 1.2] * 20,
             "split": "fit" if i < 3 else "validation"}
            for i, distance in enumerate([30., 50., 70., 40., 60.])]


def test_tof_bias_uses_fit_only_and_rejects_bad_validation():
    samples = range_samples()
    profile = fit_tof(samples, "sensor-1", .5, -.3)
    assert validate_tof_profile(profile)["bias_cm"] == pytest.approx(1.2)
    assert profile["sensor_z_cm"] == .5
    samples[-1]["raw_cm"] = [55.] * 20
    with pytest.raises(ValueError, match="held-out"):
        fit_tof(samples, "sensor-1")
    samples[-1]["reference_cm"] = float("nan")
    with pytest.raises(ValueError, match="distinct reference"):
        fit_tof(samples, "sensor-1")


def test_frontal_pose_accounts_for_face_model_axis_rotation():
    assert frontal_pose(179., 2.) and frontal_pose(-178., -2.)
    assert not frontal_pose(150., 0.)
    assert not frontal_pose(180., 25.)
    assert not frontal_pose(float("nan"), 0.)


def test_profiles_are_atomic_and_detect_modified_data(tmp_path):
    store = CalibrationStore(tmp_path)
    record = camera_record(lens(), 0)
    store.save("driver_0", record)
    with pytest.raises(ValueError):
        store.save("driver_0", {"broken": float("nan")})
    assert store.load("driver_0") == record
    data = json.loads((tmp_path / "driver_0.json").read_text())
    data["data"]["camera_index"] = 2
    (tmp_path / "driver_0.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Corrupt"):
        store.load("driver_0")


def test_rig_bindings_reject_component_replacement_and_lcd_changes():
    transform, samples = pose_samples()
    setup = {"panel_cm": [40, 25], "display": {"name": "LCD", "logical_resolution": [1600, 900]},
             "road_indices": [1, 2], "stereo_fingerprint": "intrinsics-and-stereo-v1"}
    rig = {"binding": copy.deepcopy(setup), "poses": {"road": fit_installed_pose(samples, lens(), "road")},
           "panel": fit_panel_mapping(panel_samples(), 40, 25)}
    assert not rig_compatibility_errors(rig, setup, False, True)
    setup["road_indices"] = [2, 1]
    assert any("selection/calibration changed" in e for e in rig_compatibility_errors(rig, setup, False, True))
    setup["display"]["logical_resolution"] = [1280, 720]
    assert any("display mode changed" in e for e in rig_compatibility_errors(rig, setup, False, True))
