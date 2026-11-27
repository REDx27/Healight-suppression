"""Tests for fail-safe secondary-display blocker output."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
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


def test_lcd_clear_state_and_alignment_patterns_are_explicit():
    app = _application()
    blocker = LCDBlockerWindow()
    blocker.configure_panel(40.0, 20.0, (1600, 900), radius_px=30.0)
    blocker.enable_for_testing()

    assert blocker.clear_state == "white"
    blocker.show_test_pattern("center")
    assert [(spot.x_px, spot.y_px) for spot in blocker.spots] == [(800, 450)]

    blocker.show_test_pattern("corners")
    assert len(blocker.spots) == 5
    assert (800, 450) in {
        (spot.x_px, spot.y_px) for spot in blocker.spots
    }

    blocker.set_clear_state("black")
    assert blocker.clear_state == "black"
    assert blocker.spots == ()
    blocker.show_test_pattern("clear")
    assert blocker.spots == ()

    with pytest.raises(ValueError, match="clear state"):
        blocker.set_clear_state("transparent")
    blocker.disable_output()
    app.processEvents()


def test_unchanged_lcd_frames_and_empty_clears_do_not_request_repaint(monkeypatch):
    app = _application()
    blocker = LCDBlockerWindow()
    blocker.enable_for_testing()
    paints = []
    monkeypatch.setattr(blocker, "update", lambda: paints.append(True))
    for _ in range(200):
        blocker.clear_output()
    assert not paints
    blocker.update_intersections([(0., 0., 10.)])
    for _ in range(200):
        blocker.update_intersections([(0., 0., 10.)])
    assert len(paints) == 1
    blocker.clear_output()
    blocker.clear_output()
    assert len(paints) == 2
    blocker.set_clear_state("black")
    assert len(paints) == 3  # Background changes must paint even without spots.
    blocker.close()
    app.processEvents()


def test_panel_configuration_updates_radius_and_invalidates_old_pixel_geometry():
    app = _application()
    blocker = LCDBlockerWindow()
    blocker.configure_panel(40., 20., (1600, 900), 30.)
    blocker.enable_for_testing()
    blocker.update_intersections([(0., 0., 10.)])
    blocker.configure_panel(40., 20., (1600, 900), 45.)
    assert blocker.spots[0].radius_px == 45.
    blocker.show_alignment_mark((.5, .5))
    blocker.configure_panel(40., 20., (1600, 900), 45.)
    assert blocker.spots[0].radius_px == 7.  # Reapplying config preserves jig marks.
    blocker.configure_panel(40., 20., (1920, 1080), 45.)
    assert blocker.spots == ()
    blocker.update_intersections([(0., 0., 10.)])
    mapping = [[1 / 40., 0., .5], [0., -1 / 20., 1.]]
    blocker.set_pixel_mapping(mapping)
    assert blocker.spots == ()
    blocker.close()
    app.processEvents()


@pytest.mark.parametrize("width,height,radius", [(float("nan"), 20., 30.),
                                                  (40., float("inf"), 30.),
                                                  (40., 20., float("nan"))])
def test_nonfinite_panel_dimensions_and_radius_are_rejected(width, height, radius):
    app = _application()
    blocker = LCDBlockerWindow()
    with pytest.raises(ValueError):
        blocker.configure_panel(width, height, (1600, 900), radius)
    blocker.close()
    app.processEvents()
