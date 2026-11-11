"""Off-screen regression tests for the main session workflow."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QSizePolicy

from glare_tracker.operating_modes import OperatingMode, SessionState
from glare_tracker.capture import CameraDevice, parse_directshow_camera_names
from glare_tracker.window import MainWindow, camera_roles_for_devices


def _application():
    return QApplication.instance() or QApplication([])


def test_directshow_names_and_locked_integrated_driver_roles():
    output = """
[dshow @ 1] "Integrated Camera" (video)
[dshow @ 1] "USB Camera" (video)
[dshow @ 1] "USB Camera" (video)
[dshow @ 1] "Microphone Array" (audio)
"""
    assert parse_directshow_camera_names(output) == [
        "Integrated Camera", "USB Camera", "USB Camera"]
    devices = [
        CameraDevice(0, 640, 480, "DirectShow", "USB Camera"),
        CameraDevice(1, 640, 480, "DirectShow", "USB Camera"),
        CameraDevice(2, 640, 480, "DirectShow", "Integrated Camera"),
    ]
    assert camera_roles_for_devices(
        devices, preferred_driver=0, preferred_primary=2,
        preferred_secondary=1, lock_integrated=True,
    ) == (2, 0, 1)


def test_manual_session_run_standby_stop_policy():
    app = _application()
    window = MainWindow()
    assert window.camera_feeds.maximumHeight() == 480
    assert window.camera_feeds.driver.minimumWidth() == 180
    assert window.camera_feeds.driver.maximumWidth() == 16777215
    assert (window.camera_feeds.sizePolicy().verticalPolicy()
            == QSizePolicy.Ignored)
    assert (window.bottom_splitter.sizePolicy().verticalPolicy()
            == QSizePolicy.Ignored)
    assert window.camera_feeds.headlight.status_badge.minimumWidth() == 74
    assert window.camera_feeds.headlight.detail.minimumHeight() == 28
    assert window.camera_feeds.headlight.detail.maximumHeight() == 48
    assert window.visual_splitter.orientation() == Qt.Vertical
    assert window.workspace.telemetry is None
    assert window.readout.parent() is window.bottom_splitter
    assert window.camera_feeds.parent() is window.bottom_splitter
    assert (window.camera_feeds.driver.viewport.sizePolicy().verticalPolicy()
            == QSizePolicy.Ignored)
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.FULLY_MANUAL.value)

    window._set_session_state(SessionState.RUN)
    initial_eye = window.controls.get_manual_eye_pos()
    assert window._session_state is SessionState.RUN
    assert window.tracker.last_eye_cm == initial_eye
    assert window.controls.btn_play_movement.isEnabled()
    assert not window.cap_thread.isRunning()
    assert window.headlight_thread is None

    window._set_session_state(SessionState.STANDBY)
    window.controls.spin_driver_x.setValue(initial_eye[0] + 10.0)
    app.processEvents()
    assert window._session_state is SessionState.STANDBY
    assert window.tracker.last_eye_cm == initial_eye
    assert not window.controls.btn_play_movement.isEnabled()

    window._set_session_state(SessionState.RUN)
    assert window.tracker.last_eye_cm == window.controls.get_manual_eye_pos()

    window._set_session_state(SessionState.STOP)
    assert window._session_state is SessionState.STOP
    assert window.tracker.last_eye_cm is None
    assert window.header.btn_stop.isChecked()
    window.close()


def test_editor_regions_expand_and_reflow_without_outer_card_margins():
    app = _application()
    window = MainWindow()
    window.resize(1500, 900)
    window.show()
    app.processEvents()

    margins = window.centralWidget().layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        0, 0, 0, 0)
    assert window.header.height() == 54
    assert window.main_splitter.orientation() == Qt.Horizontal
    assert window.sidebar.width() >= 390

    window.resize(1000, 700)
    app.processEvents()
    assert window.main_splitter.orientation() == Qt.Vertical
    window.close()


def test_scene_grid_has_unique_divisions_and_viewport_toggle():
    app = _application()
    window = MainWindow()
    scene = window.scene_3d

    minor = scene._grid_segments(240, 10, exclude_multiple=40).reshape(-1, 2, 3)
    major = scene._grid_segments(240, 40).reshape(-1, 2, 3)
    minor_segments = {tuple(segment.flatten()) for segment in minor}
    major_segments = {tuple(segment.flatten()) for segment in major}
    assert len(minor_segments) == len(minor)
    assert len(major_segments) == len(major)
    assert minor_segments.isdisjoint(major_segments)

    assert scene._grid_visible
    scene.grid_button.click()
    app.processEvents()
    assert not scene._grid_visible
    assert not scene._minor_grid.visible()
    assert not scene._major_grid.visible()
    assert scene.grid_button.toolTip() == "Show ground grid"
    scene.grid_button.click()
    assert scene._grid_visible
    assert scene._minor_grid.visible()
    assert scene._major_grid.visible()
    window.close()


def test_switching_driver_source_clears_manual_coordinate():
    app = _application()
    window = MainWindow()
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.FULLY_MANUAL.value)
    window._set_session_state(SessionState.RUN)
    assert window.tracker.last_eye_cm is not None

    # Avoid starting physical cameras in this policy-only test.
    window._set_session_state(SessionState.STOP)
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.HEADLIGHT_FIXED.value)
    app.processEvents()
    assert window.tracker.last_eye_cm is None
    window.close()


def test_custom_detection_panel_and_feed_preview_controls():
    app = _application()
    window = MainWindow()

    settings = window.controls.get_light_detection_settings()
    assert settings.max_sources == 4
    assert settings.brightness_threshold == 200
    assert settings.blur_size == 3
    assert settings.local_contrast_threshold == 8
    assert settings.minimum_confidence == 0.25
    assert settings.adaptive_threshold is True
    assert not window.controls.light_detection_group.isHidden()
    assert window.camera_feeds.headlight.preview_combo.currentText() == (
        "Detection overlay")
    assert window.camera_feeds.headlight.preview_combo.count() == 9
    assert settings.require_local_contrast is True

    window.controls.btn_daylight_phone_preset.click()
    preset = window.controls.get_light_detection_settings()
    assert preset.require_local_contrast is True
    assert preset.local_contrast_threshold == 8
    assert preset.max_area_px == 50000
    assert preset.minimum_confidence == 0.25
    assert preset.max_sources == 4
    assert preset.background_rejection is False
    assert window.camera_feeds.headlight.preview_combo.currentText() == (
        "Detection overlay")

    window.controls.spin_min_light_area.setValue(14)
    window.controls.spin_max_light_area.setValue(5)
    assert (window.controls.spin_max_light_area.value()
            >= window.controls.spin_min_light_area.value())

    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.HEADLIGHT_FIXED.value)
    app.processEvents()
    assert window.controls.light_detection_group.isHidden()
    window.close()


def test_available_camera_dropdowns_assign_roles_with_fixed_driver():
    app = _application()
    window = MainWindow()

    devices = [
        CameraDevice(0, 640, 480, "DirectShow"),
        CameraDevice(2, 1280, 720, "Media Foundation"),
    ]
    window.controls.set_available_cameras(devices)
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.DRIVER_FIXED.value)
    window.controls.combo_detection_setup.setCurrentText("Single Camera")
    window.controls.spin_driver_camera.setValue(2)
    window.controls.spin_headlight_camera.setValue(0)
    app.processEvents()

    policy = window.controls.mode_policy()
    assert window.controls.spin_driver_camera.count() == 2
    assert "1280×720" in window.controls.spin_driver_camera.currentText()
    assert "640×480" in window.controls.spin_headlight_camera.currentText()
    assert window.controls.spin_driver_camera.value() == 2
    assert window.controls.spin_headlight_camera.value() == 0
    assert policy.manual_driver is True
    assert policy.use_driver_camera is False
    assert policy.use_road_camera is True
    assert not window.cap_thread.isRunning()
    window.close()


def test_named_camera_labels_and_new_installation_defaults():
    app = _application()
    window = MainWindow()
    devices = [
        CameraDevice(0, 640, 480, "DirectShow", "Integrated Camera"),
        CameraDevice(1, 640, 480, "DirectShow", "USB Camera"),
        CameraDevice(2, 640, 480, "DirectShow", "USB Camera"),
    ]
    window._on_cameras_discovered(devices)
    app.processEvents()

    assert window.controls.check_lock_driver_camera.isChecked()
    assert not window.controls.spin_driver_camera.isEnabled()
    assert window.controls.spin_driver_camera.value() == 0
    assert window.controls.spin_headlight_camera.value() == 1
    assert window.controls.spin_headlight_camera_2.value() == 2
    assert "Integrated Camera" in window.controls.spin_driver_camera.currentText()
    assert "USB Camera" in window.controls.spin_headlight_camera.currentText()
    window.close()
