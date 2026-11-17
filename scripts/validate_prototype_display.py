"""Live, non-camera smoke test for the prototype-display lifecycle.

Run this with the prototype monitor connected in Windows Extend mode. The test
briefly opens GlareTracker, activates the selected non-primary display, enters
Standby, resumes Run, and enters Stop. It prints the observed target screen and
whether the fullscreen output was released at each state.
"""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from glare_tracker.operating_modes import OperatingMode, SessionState
from glare_tracker.window import MainWindow


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    screens = app.screens()
    if len(screens) < 2:
        print("FAIL: Qt detects no non-primary display.", flush=True)
        return 2

    window = MainWindow(discover_cameras=False)
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.FULLY_MANUAL.value)
    window.controls.check_lcd_output.setChecked(True)
    window._refresh_available_lcd_displays()
    window.show()

    observations: dict[str, bool] = {}
    profile = window.controls.selected_panel_dimension_profile()
    print(
        "PANEL-PRESET: "
        f"name={profile.get('name')}, "
        f"dimensions=({window.controls.spin_ws_w.value():.2f}, "
        f"{window.controls.spin_ws_h.value():.2f}) cm, "
        f"locked={not window.controls.spin_ws_w.isEnabled()}",
        flush=True,
    )

    def enter_run():
        window._set_session_state(SessionState.RUN)

    def verify_run(label: str):
        blocker = window.lcd_blocker
        handle = blocker.windowHandle()
        screen_name = handle.screen().name() if handle and handle.screen() else "none"
        selected_name = window.controls.combo_lcd_display.currentData()
        passed = (
            blocker.output_enabled
            and blocker.isVisible()
            and blocker.isFullScreen()
            and screen_name == selected_name
        )
        observations[label] = passed
        print(
            f"{label}: enabled={blocker.output_enabled}, visible={blocker.isVisible()}, "
            f"fullscreen={blocker.isFullScreen()}, screen={screen_name}, "
            f"selected={selected_name}, resolution={blocker.resolution}",
            flush=True,
        )

    def enter_standby():
        window._set_session_state(SessionState.STANDBY)

    def verify_hidden(label: str):
        blocker = window.lcd_blocker
        passed = not blocker.output_enabled and blocker.isHidden()
        observations[label] = passed
        print(
            f"{label}: enabled={blocker.output_enabled}, hidden={blocker.isHidden()}",
            flush=True,
        )

    def enter_stop():
        window._set_session_state(SessionState.STOP)

    def finish():
        verify_hidden("STOP")
        passed = all(observations.values()) and len(observations) == 4
        print(
            "PASS: prototype display follows Run/Standby/Stop safely."
            if passed else
            f"FAIL: lifecycle observations={observations}",
            flush=True,
        )
        window.close()
        app.exit(0 if passed else 1)

    QTimer.singleShot(400, enter_run)
    QTimer.singleShot(900, lambda: verify_run("RUN-1"))
    QTimer.singleShot(1400, enter_standby)
    QTimer.singleShot(1750, lambda: verify_hidden("STANDBY"))
    QTimer.singleShot(2150, enter_run)
    QTimer.singleShot(2650, lambda: verify_run("RUN-2"))
    QTimer.singleShot(3100, enter_stop)
    QTimer.singleShot(3450, finish)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
