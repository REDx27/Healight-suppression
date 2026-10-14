"""Regression coverage for independent left/right-eye glare geometry."""

from types import SimpleNamespace

import pytest

from glare_tracker.tracking import TrackingController


class _Scene:
    def update_eyes(self, eyes):
        self.eyes = tuple(eyes)

    def update_lights(self, lights):
        self.lights = tuple(lights)

    def update_eye_rays(self, eyes, lights):
        self.rays = tuple((eye, light) for light in lights for eye in eyes)

    def update_intersections(self, intersections):
        self.intersections = tuple(intersections)


class _Windshield:
    def update_glares(self, glares, has_out):
        self.glares = tuple(glares)
        self.has_out = has_out

    def clear_glare(self):
        self.glares = ()


class _Readout:
    def __init__(self):
        self.values = {}
        self.intersections = ()

    def set_value(self, key, value, color=None):
        self.values[key] = value

    def set_intersections(self, intersections):
        self.intersections = tuple(intersections)


class _Controls:
    def get_light_positions(self):
        return [(0.0, 100.0, 10.0)]

    def get_windshield_dims(self):
        return (40.0, 20.0)

    def mode_policy(self):
        return SimpleNamespace(manual_driver=False)


def test_head_roll_produces_two_vertically_separated_intersections():
    scene = _Scene()
    windshield = _Windshield()
    readout = _Readout()
    tracker = TrackingController(scene, windshield, readout, _Controls())

    # The midpoint is already at the centre reference, while Eye 1 is lower
    # and Eye 2 is higher. This models a rolled/tilted head.
    tracker.on_eyes_detected(
        -3.0, -50.0, 8.0,
        3.0, -50.0, 12.0,
    )

    assert tracker.last_eyes_cm == (
        (-3.0, -50.0, 8.0),
        (3.0, -50.0, 12.0),
    )
    assert len(scene.rays) == 2
    assert len(readout.intersections) == 2
    assert [entry[0] for entry in readout.intersections] == ["L1/E1", "L1/E2"]

    first = readout.intersections[0][1]
    second = readout.intersections[1][1]
    assert first[0] == pytest.approx(-2.0)
    assert second[0] == pytest.approx(2.0)
    assert first[2] == pytest.approx(8.0 + 2.0 / 3.0)
    assert second[2] == pytest.approx(11.0 + 1.0 / 3.0)
    assert first[2] != second[2]

    # The front-view blocker coordinates also retain that vertical separation.
    assert len(windshield.glares) == 2
    assert windshield.glares[0][1] != windshield.glares[1][1]
