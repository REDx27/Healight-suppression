"""Off-screen regression tests for the main session workflow."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QSizePolicy

from glare_tracker.operating_modes import OperatingMode, SessionState
from glare_tracker.window import MainWindow


def _application():
    return QApplication.instance() or QApplication([])


def test_manual_session_run_standby_stop_policy():
    app = _application()
    window = MainWindow()
    assert window.camera_feeds.maximumHeight() == 420
    assert window.camera_feeds.driver.maximumWidth() == 480
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
