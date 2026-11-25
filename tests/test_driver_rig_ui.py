"""Headless functional checks of calibration controls and physical-output gating."""

import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QSettings

import glare_tracker.window as window_module
from glare_tracker.calibration import CalibrationResult
from glare_tracker.installation import CalibrationStore, camera_record
from glare_tracker.lcd_blocker import LCDBlockerWindow
from glare_tracker.light_sources import TrackedLightSource
from glare_tracker.operating_modes import OperatingMode, SessionState
from glare_tracker.widgets.controls import ControlsPanel
from glare_tracker.widgets.driver_calibration import DriverCalibrationDialog, DriverCalibrationGuide
from glare_tracker.widgets.rig_calibration import PanelMappingPage, RigCalibrationDialog

load_distance_preferences = window_module.MainWindow._load_driver_distance_settings


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch, tmp_path):
    store = CalibrationStore(tmp_path)
    monkeypatch.setattr(window_module, "CalibrationStore", lambda: store)
    monkeypatch.setattr(window_module.MainWindow, "_load_driver_distance_settings", lambda self: None)
    monkeypatch.setattr(window_module.MainWindow, "_save_driver_distance_settings", lambda self: None)
    result = window_module.MainWindow(discover_cameras=False)
    # Exercise actual state/config handling without opening physical cameras or HDMI.
    monkeypatch.setattr(result, "_ensure_required_cameras", result._push_config)
    monkeypatch.setattr(result, "_activate_lcd_output", lambda force=False: False)
    yield result
    result.close()


def model():
    return CalibrationResult(np.array([[600., 0, 320], [0, 600., 240], [0, 0, 1]]),
                             np.zeros(5), (640, 480), .2)


@pytest.mark.parametrize("mode, road, driver", [
    (OperatingMode.FULLY_AUTO, True, True),
    (OperatingMode.DRIVER_FIXED, True, False),
    (OperatingMode.HEADLIGHT_FIXED, False, True),
    (OperatingMode.FULLY_MANUAL, False, False),
])
def test_calibration_actions_follow_mode(app, mode, road, driver):
    controls = ControlsPanel()
    controls.combo_operating_mode.setCurrentText(mode.value)
    assert controls.btn_stereo_calibration.isHidden() is not road
    assert controls.btn_driver_calibration.isHidden() is not driver
    assert not controls.btn_rig_calibration.isHidden()
    controls.close()


def test_driver_camera_save_and_skips_are_independent(app, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    store = CalibrationStore(tmp_path)
    dialog = DriverCalibrationDialog(0, store)
    assert "not connected" in dialog.tof_indicator.text()
    assert not dialog.use_saved_camera.isEnabled()
    dialog._skip("tof")
    assert dialog.skips == {"camera": False, "tof": True}
    dialog._skip("camera")
    assert "SKIPPED" in dialog.camera_indicator.text()
    dialog._camera_fitted(model())
    assert store.load("driver_0") is None  # Fit is not activation.
    dialog._save_camera()
    assert store.load("driver_0")["pixel_convention"] == "native_unmirrored"
    assert dialog.skips == {"camera": False, "tof": True}
    dialog._skip("camera")
    dialog.use_saved_camera.click()
    assert not dialog.skips["camera"]
    dialog._reset_camera_views()
    assert store.load("driver_0") is not None
    dialog.reject()


def test_no_controller_cannot_pass_tof_calibration(app, tmp_path):
    store = CalibrationStore(tmp_path)
    dialog = DriverCalibrationDialog(0, store)
    dialog.offsets_confirmed.setChecked(True)
    dialog._capture_range()
    assert "20 fresh valid readings" in dialog.range_message.text()
    dialog._save_tof()
    assert store.load("tof") is None
    assert "Not calibrated" not in dialog.tof_indicator.text() or not dialog.saved_tof
    dialog.reject()


def test_driver_guide_has_ordered_separate_sections(app):
    guide = DriverCalibrationGuide()
    from PyQt5.QtWidgets import QTabWidget
    tabs = guide.findChild(QTabWidget)
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["1. Camera", "2. ToF sensor"]
    guide.reject()


def test_rig_cannot_save_incomplete_poses_or_unmeasured_lcd(app, tmp_path):
    store = CalibrationStore(tmp_path)
    dialog = RigCalibrationDialog({"panel_cm": [40, 25]},
                                  {"road": (1, model()), "driver": (0, None)},
                                  store, lambda uv: False)
    assert not dialog.pages["driver"].start.isEnabled()
    dialog._save()
    assert "confirm" in dialog.status.text()
    dialog.identity_confirm.setChecked(True)
    dialog._save()
    assert "Fit every required" in dialog.status.text()
    assert store.load("rig") is None
    dialog.reject()


def test_panel_marks_require_real_display_request_and_measurement_confirmation(app):
    shown = []
    page = PanelMappingPage(40, 25, lambda uv: shown.append(uv) or True)
    page.confirm.setChecked(True)
    page._capture()
    assert not page.samples
    page._show()
    page.confirm.setChecked(False)
    page._capture()
    assert not page.samples
    page.x.setValue(-16)
    page.z.setValue(22.5)
    page.confirm.setChecked(True)
    page._capture()
    assert len(page.samples) == 1 and shown == [(.1, .1)]
    page._undo()
    assert not page.samples and page.shown_index is None
    page.close()


def test_main_calibration_buttons_open_their_actual_dialogs(window, monkeypatch):
    opened = []

    class Driver:
        def __init__(self, index, store, skips, parent):
            self.skips = {"camera": False, "tof": True}
            opened.append(("driver", index))

        def exec_(self):
            return 0

        def deleteLater(self):
            pass

    class Rig(Driver):
        def __init__(self, setup, models, store, show_mark, parent):
            opened.append(("rig", set(models)))

    monkeypatch.setattr(window_module, "DriverCalibrationDialog", Driver)
    monkeypatch.setattr(window_module, "RigCalibrationDialog", Rig)
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.FULLY_AUTO.value)
    window.controls.btn_driver_calibration.click()
    window.controls.btn_rig_calibration.click()
    assert opened[0][0] == "driver" and opened[1] == ("rig", {"road", "driver"})
    assert window._driver_skips["tof"]


def test_standby_to_run_preserves_worker_generation_and_rejects_queued_frame(window):
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.HEADLIGHT_FIXED.value)
    window._set_session_state(SessionState.STANDBY)
    generation = window._installation_generation
    old_capture = time.monotonic_ns()
    window._set_session_state(SessionState.RUN)
    assert window._installation_generation == generation == window.cap_thread._config.generation
    payload = {"generation": generation, "captured_ns": old_capture, "valid": True,
               "eyes": ((1., -50., 10.), (7., -50., 11.)), "frame": "demo",
               "depth_source": "camera-only"}
    window._on_driver_observation(payload)
    assert window._last_driver_observed_ns is None
    payload["captured_ns"] = time.monotonic_ns()
    window._on_driver_observation(payload)
    assert window.tracker.last_eyes_cm is not None
    assert not window.lcd_blocker.tracking_authorized  # Demonstration != measured rig.
    window._set_session_state(SessionState.STOP)
    window._on_driver_observation(payload)
    assert window.tracker.last_eyes_cm is None


def test_installed_coordinates_bypass_demo_recentering(window):
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.HEADLIGHT_FIXED.value)
    tracker = window.tracker
    tracker.installed_coordinates = True
    eyes = ((8., -57., 16.), (14., -57., 17.))
    tracker.on_eyes_detected(*eyes[0], *eyes[1])
    assert tracker.last_eyes_cm == eyes
    tracker.calibrate()  # The old centre button must not shift measured coordinates.
    assert tracker.last_eyes_cm == eyes


def test_physical_output_expires_and_requires_lcd_frames_and_time_pair(window, monkeypatch):
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.FULLY_AUTO.value)
    window.controls.check_live_driver_distance.setChecked(True)
    monkeypatch.setattr(window, "_installation_errors", lambda *args: [])
    now = time.monotonic_ns()
    window._last_driver_observed_ns = now - 10_000_000
    window._last_road_observed_ns = now - 20_000_000
    window._driver_lcd_frame_valid = window._road_lcd_frame_valid = True
    window._guard_physical_observation_pair(now)
    assert window.lcd_blocker.tracking_authorized
    window._guard_physical_observation_pair(now + 250_000_000)
    assert not window.lcd_blocker.tracking_authorized
    window._driver_lcd_frame_valid = False
    window._guard_physical_observation_pair(now)
    assert not window.lcd_blocker.tracking_authorized
    window._driver_lcd_frame_valid = True
    window._last_road_observed_ns = now - 90_000_000
    window._guard_physical_observation_pair(now)
    assert not window.lcd_blocker.tracking_authorized
    window._last_road_observed_ns = now - 20_000_000
    window._tof_profile = {"device_id": "tof-1"}
    window._last_range_observed_ns = now - 25_000_000
    window._tof_worker = SimpleNamespace(latest={"device_id": "tof-1", "valid": True,
                                               "observed_ns": now - 25_000_000}, stop=lambda: True)
    window._guard_physical_observation_pair(now)
    assert window.lcd_blocker.tracking_authorized
    window._tof_worker.latest["valid"] = False
    window._guard_physical_observation_pair(now)
    assert not window.lcd_blocker.tracking_authorized  # Do not wait for the old good range to expire.
    window._session_state = SessionState.RUN
    source = TrackedLightSource("L1", (0., 200., 10.), time.time(), 1., "tracked", (320., 240.), 5.)
    payload = {"sources": [source], "captured_ns": time.monotonic_ns(),
               "generation": window._installation_generation, "frame": "lcd", "pair_skew_ns": 10_000_000}
    window._on_road_observation(payload)
    assert window._last_road_observed_ns == payload["captured_ns"]
    window._on_road_observation({**payload, "pair_skew_ns": 80_000_000})
    assert window._last_road_observed_ns is None and not window.lcd_blocker.tracking_authorized


def test_real_lcd_mapping_changes_pixels_and_gate_clears_output(app):
    output = LCDBlockerWindow()
    output.configure_panel(40, 25, (1600, 900), 12)
    output.enable_for_testing()
    output.set_pixel_mapping([[1 / 40, 0, .499], [0, -1 / 25, 1]])
    output.update_intersections([(0, 0, 12.5)])
    assert output.spots[0].x_px == 798 and output.spots[0].y_px == 450
    output.tracking_authorized = False
    output.update_intersections([(0, 0, 12.5)])
    assert not output.spots
    output.close()


def test_toolbar_center_references_current_eyes_and_keeps_feedback_visible(window):
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.HEADLIGHT_FIXED.value)
    window._set_session_state(SessionState.RUN)
    assert not window.header.btn_calibrate.isEnabled()
    payload = {"generation": window._installation_generation, "valid": True, "frame": "demo",
               "eyes": ((0., -50., 10.), (6., -50., 12.)), "depth_source": "Fixed/reference distance"}
    window._on_driver_observation({**payload, "captured_ns": time.monotonic_ns()})
    moved = {**payload, "eyes": ((4., -50., 14.), (10., -50., 16.))}
    window._on_driver_observation({**moved, "captured_ns": time.monotonic_ns()})
    assert window.header.btn_calibrate.isEnabled()
    window.header.btn_calibrate.click()
    assert window.tracker.last_eye_cm == pytest.approx((0., -50., window.controls.spin_ws_h.value() / 2))
    assert "Centre reference set" in window.statusBar().currentMessage()
    window._on_driver_observation({**moved, "captured_ns": time.monotonic_ns()})
    assert "Centre reference set" in window.statusBar().currentMessage()
    window._on_eye_lost()
    assert not window.header.btn_calibrate.isEnabled()
    assert window._calibrate_center() is False


def test_toolbar_center_expires_and_does_not_shift_installed_coordinates(window):
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.HEADLIGHT_FIXED.value)
    window._set_session_state(SessionState.RUN)
    payload = {"generation": window._installation_generation, "valid": True, "frame": "demo",
               "eyes": ((8., -57., 16.), (14., -57., 17.)), "depth_source": "Fixed/reference distance"}
    window._on_driver_observation({**payload, "captured_ns": time.monotonic_ns()})
    window._last_driver_observed_ns -= 300_000_000
    window._expire_installed_observations()
    assert not window.header.btn_calibrate.isEnabled()
    assert window._calibrate_center() is False
    window._on_driver_observation({**payload, "frame": "lcd", "captured_ns": time.monotonic_ns()})
    eyes = window.tracker.last_eyes_cm
    assert not window.header.btn_calibrate.isEnabled()
    assert "Installed rig" in window.header.btn_calibrate.toolTip()
    assert window._calibrate_center() is False
    assert window.tracker.last_eyes_cm == eyes


def test_distance_toggle_updates_config_and_invalidates_previous_observations(window):
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.HEADLIGHT_FIXED.value)
    window._set_session_state(SessionState.RUN)
    generation = window._installation_generation
    window.controls.spin_eye_dist.setValue(65.)
    assert window.controls.spin_eye_dist.isEnabled()
    assert not window.cap_thread._config.live_driver_distance
    assert window.cap_thread._config.eye_dist_cm == 65.
    assert window._installation_generation > generation
    window.controls.check_live_driver_distance.setChecked(True)
    assert window.cap_thread._config.live_driver_distance
    assert not window.controls.spin_eye_dist.isEnabled()
    assert not window.header.btn_calibrate.isEnabled()
    window.controls.check_live_driver_distance.setChecked(False)
    assert window.cap_thread._config.eye_dist_cm == 65.
    assert window.cap_thread._config.tof_profile is None
    assert window._tof_worker is None
    assert "fixed 65.0" in window.controls.driver_calibration_status.text()


def test_distance_preferences_load_without_triggering_measurement_or_overwriting_values(window, tmp_path):
    settings = QSettings(str(tmp_path / "driver.ini"), QSettings.IniFormat)
    settings.setValue("driver_distance/live", True)
    settings.setValue("driver_distance/fixed_cm", 62.5)
    window._camera_role_settings = settings
    generation = window._installation_generation
    # Exercise the real loader; the fixture disables startup reads of user preferences.
    load_distance_preferences(window)
    assert window.controls.check_live_driver_distance.isChecked()
    assert window.controls.spin_eye_dist.value() == 62.5
    assert not window.controls.spin_eye_dist.isEnabled()
    assert window._installation_generation == generation
    assert settings.value("driver_distance/fixed_cm", type=float) == 62.5
