"""Regression checks for the toolbar's centre-reference operation."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from glare_tracker.tracking import TrackingController


def controller():
    controls = SimpleNamespace(
        get_windshield_dims=lambda: (40., 20.),
        get_light_positions=lambda: [(0., 100., 10.)],
        mode_policy=lambda: SimpleNamespace(manual_driver=False),
        is_auto_light=lambda: False,
    )
    return TrackingController(Mock(), Mock(), Mock(), controls)


def test_center_recomputes_midpoint_and_intersections_immediately():
    tracker = controller()
    tracker.on_eye_detected(2., -50., 15.)
    tracker.on_eye_detected(8., -50., 18.)
    assert tracker.last_eye_cm == (6., -50., 13.)
    success = tracker.calibrate()
    assert tracker.last_eye_cm == (0., -50., 10.)
    assert success is True
    assert tracker._scene_3d.update_eyes.call_args.args[0] == ((0., -50., 10.),)


def test_center_rejects_lost_face_and_does_not_reuse_old_observations():
    tracker = controller()
    tracker.on_eye_detected(2., -50., 15.)
    offset = tracker._calibration_offset
    tracker.on_eye_lost()
    assert tracker.last_observed_eye_cm is None
    assert tracker.calibrate() is False
    assert tracker._calibration_offset == offset
    assert tracker.last_eye_cm is None


def test_center_retains_both_eyes_and_their_vertical_separation():
    tracker = controller()
    tracker.on_eyes_detected(-1., -50., 7., 5., -50., 11.)
    tracker.on_eyes_detected(2., -50., 9., 8., -50., 13.)
    assert tracker.calibrate() is True
    left, right = tracker.last_eyes_cm
    assert left == pytest.approx((-3., -50., 8.))
    assert right == pytest.approx((3., -50., 12.))


def test_center_never_moves_installed_rig_coordinates():
    tracker = controller()
    tracker.installed_coordinates = True
    tracker.on_eyes_detected(8., -57., 16., 14., -57., 17.)
    original = tracker.last_eyes_cm
    assert tracker.calibrate() is False
    assert tracker.last_eyes_cm == original
