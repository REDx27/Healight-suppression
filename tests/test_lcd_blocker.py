"""Tests for fail-safe secondary-display blocker output."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from glare_tracker.lcd_blocker import LCDBlockerWindow
from glare_tracker.tracking import TrackingController


class _Scene:
    def hide_tracking(self):
        pass

    def update_eyes(self, eyes):
        pass

    def update_lights(self, lights):
        pass

    def update_eye_rays(self, eyes, lights):
        pass

    def update_intersections(self, intersections):
        self.intersections = tuple(intersections)


class _Windshield:
    def update_glares(self, glares, has_out):
        pass

    def clear_glare(self):
        pass


class _Readout:
    def set_value(self, key, value, color=None):
        pass

    def set_intersections(self, intersections):
        pass


class _Controls:
    def get_windshield_dims(self):
        return 40.0, 20.0

    def get_light_positions(self):
        return [(0.0, 100.0, 10.0)]

    def is_auto_light(self):
        return False

    def mode_policy(self):
        return SimpleNamespace(manual_driver=False)


def _application():
    return QApplication.instance() or QApplication([])


def test_lcd_maps_valid_intersections_and_returns_to_white_safe_state():
    app = _application()
    blocker = LCDBlockerWindow()
    blocker.configure_panel(40.0, 20.0, (1920, 1080), radius_px=35.0)
    blocker.enable_for_testing()

    blocker.update_intersections(
        [(0.0, 0.0, 10.0), (20.0, 0.0, 0.0), (21.0, 0.0, 10.0)]
    )

    assert blocker.output_enabled
    assert len(blocker.spots) == 2
    assert blocker.spots[0].x_px == 960
    assert blocker.spots[0].y_px == 540
    assert blocker.spots[1].x_px == 1919
    assert blocker.spots[1].y_px == 1079
    assert blocker.spots[0].radius_px == 35.0

    blocker.disable_output()
    assert not blocker.output_enabled
    assert blocker.spots == ()
    assert blocker.isHidden()
    app.processEvents()


def test_tracking_controller_updates_and_clears_lcd_output():
    app = _application()
    blocker = LCDBlockerWindow()
    blocker.configure_panel(40.0, 20.0, (1920, 1080), radius_px=40.0)
    blocker.enable_for_testing()
    tracker = TrackingController(
        _Scene(), _Windshield(), _Readout(), _Controls(), lcd_blocker=blocker
    )

    tracker.on_manual_eye((0.0, -50.0, 10.0))
    assert len(blocker.spots) == 1
    tracker.on_eye_lost()
    assert blocker.spots == ()
    blocker.disable_output()
    app.processEvents()
