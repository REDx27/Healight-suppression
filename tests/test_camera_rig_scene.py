"""Offline, read-only pose reconstruction and rendering of the installed rig."""

import copy
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from glare_tracker.extrinsics import RigidTransform3D
from glare_tracker.scene_geometry import installed_camera_scene_poses
from glare_tracker.widgets.scene_3d import Scene3DWidget


@pytest.fixture
def saved_rig():
    setup = {"panel_cm": [44.28, 24.91], "display": None, "driver_index": 0,
             "road_indices": [1, 2], "driver_fingerprint": "driver-v1",
             "stereo_fingerprint": "stereo-v1"}
    road = RigidTransform3D([[1., 0, 0], [0, 0, 1], [0, -1, 0]],
                           [-7.675, .5, 28.], "road", "windshield")
    driver = RigidTransform3D([[-1., 0, 0], [0, 0, -1], [0, -1, 0]],
                             [0., -1.2, 28.], "driver", "windshield")
    rig = {"binding": copy.deepcopy(setup), "poses": {
        "driver": {"transform": driver.to_dict(), "report": {"passed": True}},
        "road": {"transform": road.to_dict(), "report": {"passed": True}}},
        "panel": {"xz_to_uv": [[1 / 44.28, 0, .5], [0, -1 / 24.91, 1.]]}}
    stereo = SimpleNamespace(R=np.eye(3), T=np.array([-15.35, 0., 0.]), camera_indices=(1, 2))
    return rig, setup, stereo


def test_all_centres_share_the_panels_centimetres_and_preserve_records(saved_rig):
    rig, setup, stereo = saved_rig
    original = copy.deepcopy((rig, setup))
    original_translation = stereo.T.copy()
    poses = {p.role: p for p in installed_camera_scene_poses(rig, setup, stereo)}
    assert set(poses) == {"driver", "road_left", "road_right"}
    np.testing.assert_allclose(poses["driver"].center_cm, [0, -1.2, 28])
    np.testing.assert_allclose(poses["road_left"].center_cm, [-7.675, .5, 28])
    np.testing.assert_allclose(poses["road_right"].center_cm, [7.675, .5, 28])
    separation = np.linalg.norm(np.array(poses["road_right"].center_cm) - poses["road_left"].center_cm)
    assert separation == pytest.approx(15.35)
    assert separation / setup["panel_cm"][0] == pytest.approx(15.35 / 44.28)
    np.testing.assert_allclose(np.array(poses["driver"].rotation)[:, 2], [0, -1, 0])
    np.testing.assert_allclose(np.array(poses["road_left"].rotation)[:, 2], [0, 1, 0])
    assert (rig, setup) == original
    np.testing.assert_array_equal(stereo.T, original_translation)


def test_right_camera_uses_full_rotated_stereo_extrinsics(saved_rig):
    rig, setup, stereo = saved_rig
    left = RigidTransform3D.from_dict(rig["poses"]["road"]["transform"])
    theta = np.deg2rad(17.)
    relative_rotation = np.array([[np.cos(theta), 0, np.sin(theta)],
                                  [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
    right = RigidTransform3D(left.rotation @ relative_rotation,
                            left.apply([15.35, 1., .3]), "road_right", "windshield")
    stereo_transform = left.then(right.inverse())
    stereo.R, stereo.T = stereo_transform.rotation, stereo_transform.translation_cm
    found = {p.role: p for p in installed_camera_scene_poses(rig, setup, stereo)}["road_right"]
    np.testing.assert_allclose(found.center_cm, right.translation_cm)
    np.testing.assert_allclose(found.rotation, right.rotation)


@pytest.mark.parametrize("changed,expected", [
    ("panel_cm", set()), ("display", set()),
    ("driver_fingerprint", {"road_left", "road_right"}),
    ("stereo_fingerprint", {"driver"}), ("road_indices", {"driver"}),
])
def test_changed_bindings_remove_affected_saved_camera_poses(saved_rig, changed, expected):
    rig, setup, stereo = saved_rig
    setup[changed] = {"panel_cm": [50., 25.], "display": {"name": "another display"},
                      "driver_fingerprint": "changed", "stereo_fingerprint": "changed",
                      "road_indices": [2, 1]}[changed]
    assert {p.role for p in installed_camera_scene_poses(rig, setup, stereo)} == expected


@pytest.mark.parametrize("bad_stereo", ["missing", "zero baseline", "nan", "wrong order", "bad rotation"])
def test_incomplete_stereo_cannot_fabricate_road_camera_centres(saved_rig, bad_stereo):
    rig, setup, stereo = saved_rig
    if bad_stereo == "missing":
        stereo = None
    elif bad_stereo == "zero baseline":
        stereo.T = np.zeros(3)
    elif bad_stereo == "nan":
        stereo.T[0] = float("nan")
    elif bad_stereo == "wrong order":
        stereo.camera_indices = (2, 1)
    else:
        stereo.R[0, 0] = 2.
    assert [p.role for p in installed_camera_scene_poses(rig, setup, stereo)] == ["driver"]
    assert installed_camera_scene_poses(None, setup, stereo) == ()


def test_unaccepted_installed_pose_is_not_presented_as_calibrated(saved_rig):
    rig, setup, stereo = saved_rig
    rig["poses"]["driver"]["report"]["passed"] = False
    assert {p.role for p in installed_camera_scene_poses(rig, setup, stereo)} == {"road_left", "road_right"}


def test_scene_camera_items_preserve_tracking_and_survive_manual_updates(saved_rig, monkeypatch):
    app = QApplication.instance() or QApplication([])
    rig, setup, stereo = saved_rig
    poses = installed_camera_scene_poses(rig, setup, stereo)
    scene = Scene3DWidget()
    scene.resize(1100, 700)
    scene.layout().setGeometry(scene.rect())
    eyes, lights = ((-3., -50., 12.), (3., -50., 12.)), ((0., 150., 18.),)
    scene.update_eyes(eyes)
    scene.update_lights(lights)
    scene.update_eye_rays(eyes, lights)
    rays = [line.pos.copy() for line in scene._ray_lines]
    scene.set_installed_camera_poses(poses)
    assert "confirm mounts" in scene.rig_note.text()
    assert not scene._camera_scatter.visible()
    count = len(scene.gl_view.items)
    for pose in poses:
        point, direction, label = scene._rig_camera_items[pose.role]
        assert point.visible() and direction.visible() and not label.isHidden()
        assert label.property("cameraColor").alpha() == 255 and label.font().pixelSize() == 12
        np.testing.assert_allclose(point.pos[0], pose.center_cm)
        np.testing.assert_allclose(direction.pos[1] - direction.pos[0], np.array(pose.rotation)[:, 2] * 8.)
    updates = []
    monkeypatch.setattr(scene._rig_camera_items["driver"][0], "setData", lambda **kwargs: updates.append(kwargs))
    for _ in range(20):
        scene.set_installed_camera_poses(poses)
    assert not updates
    scene.update_camera(1., 2., 3.)
    np.testing.assert_allclose(scene._rig_camera_items["driver"][0].pos[0], [0, -1.2, 28])
    assert scene._last_eye_positions == eyes and scene._last_light_positions == lights
    for old, ray in zip(rays, scene._ray_lines):
        np.testing.assert_array_equal(old, ray.pos)
    label_positions = [items[2].pos() for items in scene._rig_camera_items.values()]
    scene.gl_view.setCameraPosition(azimuth=25)
    scene._position_camera_labels()
    assert any(old != items[2].pos() for old, items in zip(label_positions, scene._rig_camera_items.values()))
    for pose in poses:
        np.testing.assert_allclose(scene._rig_camera_items[pose.role][0].pos[0], pose.center_cm)
    scene.camera_rig_toggle.setChecked(False)
    assert not any(item.visible() for items in scene._rig_camera_items.values() for item in items[:2])
    assert all(items[2].isHidden() for items in scene._rig_camera_items.values())
    scene.camera_rig_toggle.setChecked(True)
    scene._toggle_scene_theme(True)
    assert scene._installed_camera_poses == poses
    scene.hide_tracking()
    assert all(items[0].visible() for items in scene._rig_camera_items.values())
    scene.set_installed_camera_poses(())
    assert scene._camera_scatter.visible() and "uncalibrated" in scene.rig_note.text()
    np.testing.assert_allclose(scene._camera_scatter.pos[0], [1, 2, 3])
    assert len(scene.gl_view.items) == count
    scene.close()
    app.processEvents()


def test_main_window_scene_refresh_does_not_change_tracking_or_output(saved_rig, tmp_path, monkeypatch):
    import glare_tracker.window as module
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(module, "QSettings", lambda *args: QSettings(str(tmp_path / "ui.ini"), QSettings.IniFormat))
    window = module.MainWindow(discover_cameras=False)
    rig, _, stereo = saved_rig
    window._driver_fingerprint, window._stereo_fingerprint = "driver-v1", "stereo-v1"
    window._rig_profile, window._installation_stereo = rig, stereo
    rig["binding"] = window._installation_setup()
    before = (window.cap_thread._config, window._installation_generation,
              window.lcd_blocker.tracking_authorized, window.lcd_blocker.spots,
              window.tracker.last_eyes_cm, window.tracker.installed_coordinates)
    window._refresh_camera_rig_scene()
    assert len(window.scene_3d._installed_camera_poses) == 3
    assert before == (window.cap_thread._config, window._installation_generation,
                      window.lcd_blocker.tracking_authorized, window.lcd_blocker.spots,
                      window.tracker.last_eyes_cm, window.tracker.installed_coordinates)
    monkeypatch.setattr(window, "_selected_lcd_screen", lambda: SimpleNamespace(
        name=lambda: "different monitor", geometry=lambda: SimpleNamespace(width=lambda: 1600, height=lambda: 900)))
    window._refresh_camera_rig_scene()
    assert window.scene_3d._installed_camera_poses == ()
    assert before == (window.cap_thread._config, window._installation_generation,
                      window.lcd_blocker.tracking_authorized, window.lcd_blocker.spots,
                      window.tracker.last_eyes_cm, window.tracker.installed_coordinates)
    window.close()
    app.processEvents()


@pytest.fixture
def persisted_camera_rig(tmp_path, monkeypatch):
    """Use real profile files, while isolating machine settings and USB/HDMI."""
    import glare_tracker.calibration as calibration
    import glare_tracker.window as window_module
    from glare_tracker.installation import (
        CalibrationStore, camera_record, signature, stereo_signature,
    )
    from glare_tracker.operating_modes import OperatingMode

    app = QApplication.instance() or QApplication([])
    root = tmp_path / "calibration"
    root.mkdir()
    monkeypatch.setattr(calibration, "_calibration_dir", lambda: root)
    monkeypatch.setattr(window_module, "CalibrationStore",
                        lambda: CalibrationStore(root / "installation"))
    monkeypatch.setattr(window_module, "QSettings",
                        lambda *args: QSettings(str(tmp_path / "ui.ini"), QSettings.IniFormat))

    display = {"name": "BENCH-LCD", "width": 1600, "height": 900}
    screen = SimpleNamespace(
        name=lambda: display["name"],
        geometry=lambda: SimpleNamespace(width=lambda: display["width"],
                                         height=lambda: display["height"]))
    monkeypatch.setattr(window_module.MainWindow, "_available_lcd_screens", lambda self: [screen])

    def set_camera_roles(window):
        window.controls.combo_operating_mode.setCurrentText(OperatingMode.FULLY_AUTO.value)
        window.controls.spin_driver_camera.setValue(0)
        window.controls.spin_headlight_camera.setValue(1)
        window.controls.spin_headlight_camera_2.setValue(2)

    def set_panel_dimensions(window):
        window.controls.spin_ws_w.setValue(44.28)
        window.controls.spin_ws_h.setValue(24.91)

    monkeypatch.setattr(window_module.MainWindow, "_load_camera_role_settings", set_camera_roles)
    monkeypatch.setattr(window_module.MainWindow, "_load_panel_dimension_settings", set_panel_dimensions)

    matrix = np.array([[600., 0., 320.], [0., 610., 240.], [0., 0., 1.]])
    lens = calibration.CalibrationResult(matrix, np.zeros(5), (640, 480), .25)
    rotation, translation = np.eye(3), np.array([[-15.35], [0.], [0.]])
    r1, r2, p1, p2, q, _, _ = cv2.stereoRectify(
        matrix, lens.dist_coeffs, matrix, lens.dist_coeffs,
        lens.image_size, rotation, translation,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    essential = np.array([[0., 0., 0.], [0., 0., 15.35], [0., -15.35, 0.]])
    fundamental = np.linalg.inv(matrix).T @ essential @ np.linalg.inv(matrix)
    stereo = calibration.StereoCalibrationResult(
        lens, lens, rotation, translation, essential, fundamental,
        r1, r2, p1, p2, q, rms_error=.3, camera_indices=(1, 2))
    calibration.save_stereo_calibration(stereo, calibration.stereo_profile_name(1, 2))
    driver_profile = camera_record(lens, 0)
    store = CalibrationStore(root / "installation")
    store.save("driver_0", driver_profile)
    setup = {"panel_cm": [44.28, 24.91],
             "display": {"name": display["name"], "logical_resolution": [1600, 900]},
             "driver_index": 0, "road_indices": [1, 2],
             "driver_fingerprint": signature(driver_profile),
             "stereo_fingerprint": stereo_signature(stereo)}
    road_pose = RigidTransform3D(
        [[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]],
        [-7.675, .5, 28.], "road", "windshield")
    driver_pose = RigidTransform3D(
        [[-1., 0., 0.], [0., 0., -1.], [0., -1., 0.]],
        [0., -1.2, 28.], "driver", "windshield")
    accepted_report = {"passed": True, "fit_rmse_px": .3,
                       "held_out_rmse_px": .4, "held_out_max_transverse_cm": .2}
    rig = {"rig_id": "offline-bench-v1", "binding": setup,
           "poses": {"driver": {"transform": driver_pose.to_dict(), "report": accepted_report},
                     "road": {"transform": road_pose.to_dict(), "report": accepted_report}},
           "panel": {"xz_to_uv": [[1 / 44.28, 0., .5], [0., -1 / 24.91, 1.]],
                     "max_error_cm": .1}}
    store.save("rig", rig)
    before = {str(path.relative_to(root)): path.read_bytes()
              for path in root.rglob("*") if path.is_file()}
    return SimpleNamespace(app=app, module=window_module, root=root, setup=setup,
                           display=display, original_files=before)


def test_saved_three_camera_poses_restore_on_every_cold_window_start(persisted_camera_rig):
    saved = persisted_camera_rig
    for _ in range(2):
        # Construct a fresh window: no profile/pose assignment or manual reload.
        window = saved.module.MainWindow(discover_cameras=False)
        try:
            assert window._installation_setup() == saved.setup
            assert window._installation_errors(require_confirmation=False) == []
            poses = {pose.role: pose for pose in window.scene_3d._installed_camera_poses}
            assert set(poses) == {"driver", "road_left", "road_right"}
            for role, index, position in (
                ("driver", 0, [0., -1.2, 28.]),
                ("road_left", 1, [-7.675, .5, 28.]),
                ("road_right", 2, [7.675, .5, 28.]),
            ):
                assert poses[role].camera_index == index
                np.testing.assert_allclose(poses[role].center_cm, position, atol=1e-6)
                point = window.scene_3d._rig_camera_items[role][0]
                np.testing.assert_allclose(point.pos[0], position, atol=1e-6)
                assert point.visible()
            baseline = np.linalg.norm(np.array(poses["road_right"].center_cm)
                                      - poses["road_left"].center_cm)
            assert baseline == pytest.approx(15.35)
            assert baseline / saved.setup["panel_cm"][0] == pytest.approx(15.35 / 44.28)
            np.testing.assert_allclose(np.array(poses["driver"].rotation)[:, 2], [0., -1., 0.])
            np.testing.assert_allclose(np.array(poses["road_left"].rotation)[:, 2], [0., 1., 0.])
            assert not window.controls.check_rig_unchanged.isChecked()
            assert not window.lcd_blocker.tracking_authorized
            assert not window.lcd_blocker.output_enabled
            assert not window.cap_thread.isRunning()
            assert window.headlight_thread is None
        finally:
            window.close()
            saved.app.processEvents()
    after = {str(path.relative_to(saved.root)): path.read_bytes()
             for path in saved.root.rglob("*") if path.is_file()}
    assert after == saved.original_files


@pytest.mark.parametrize("changed", ["name", "resolution"])
def test_cold_load_rejects_saved_camera_poses_for_a_changed_lcd(persisted_camera_rig, changed):
    saved = persisted_camera_rig
    if changed == "name":
        saved.display["name"] = "ANOTHER-LCD"
    else:
        saved.display["width"] = 1920
        saved.display["height"] = 1080
    window = saved.module.MainWindow(discover_cameras=False)
    try:
        # Files load successfully, but their display binding no longer matches.
        assert window._driver_lens is not None
        assert window._installation_stereo is not None
        assert window._rig_profile["rig_id"] == "offline-bench-v1"
        assert window.scene_3d._installed_camera_poses == ()
        assert "Selected LCD identity or display mode changed" in window._installation_errors(False)
        assert not window.lcd_blocker.tracking_authorized
        assert not window.cap_thread.isRunning()
    finally:
        window.close()
        saved.app.processEvents()
