"""Offline, read-only pose reconstruction and rendering of the installed rig."""

import copy
from types import SimpleNamespace

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
