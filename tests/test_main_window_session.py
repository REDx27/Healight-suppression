"""Off-screen regression tests for the main session workflow."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QSizePolicy

from glare_tracker.operating_modes import OperatingMode, SessionState
from glare_tracker.capture import CameraDevice
from glare_tracker.window import MainWindow


def _application():
    return QApplication.instance() or QApplication([])


def test_manual_session_run_standby_stop_policy():
    app = _application()
    window = MainWindow()
    assert window.camera_feeds.maximumHeight() == 420
    assert window.camera_feeds.driver.maximumWidth() == 480
    assert (window.camera_feeds.sizePolicy().verticalPolicy()
            == QSizePolicy.Ignored)
    assert (window.bottom_splitter.sizePolicy().verticalPolicy()
            == QSizePolicy.Ignored)
    assert window.camera_feeds.headlight.status_badge.width() == 88
    assert window.camera_feeds.headlight.detail.height() == 38
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
    assert settings.max_sources == 1
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
    assert preset.max_sources == 1
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
