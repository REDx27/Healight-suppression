"""Unit and boundary coverage for the coordinate-geometry helpers."""

import numpy as np
import pytest

from glare_tracker.geometry import (
    compute_intersection,
    estimate_ipd_depth,
    intersection_to_pixel,
    pixel_to_cm,
    pixel_to_cm_calibrated,
)


def test_compute_intersection_crosses_windshield_plane():
    intersection = compute_intersection(
        eye_cm=(-3.0, -50.0, 8.0),
        light_cm=(6.0, 100.0, 14.0),
    )

    assert intersection == pytest.approx((0.0, 0.0, 10.0))


@pytest.mark.parametrize(
    ("eye_cm", "light_cm"),
    [
        ((0.0, -50.0, 10.0), (5.0, -50.0, 12.0)),  # parallel
        ((0.0, -50.0, 10.0), (5.0, -10.0, 12.0)),  # same side
        ((0.0, 10.0, 10.0), (5.0, 50.0, 12.0)),  # both in front
    ],
)
def test_compute_intersection_rejects_non_crossing_segments(eye_cm, light_cm):
    assert compute_intersection(eye_cm, light_cm) is None


def test_pixel_to_cm_maps_frame_centre_and_edges():
    assert pixel_to_cm(320, 240, 640, 480, 34.5, 19.5, 50.0) == pytest.approx(
        (0.0, -50.0, 9.75)
    )
    assert pixel_to_cm(0, 0, 640, 480, 34.5, 19.5, 50.0) == pytest.approx(
        (-17.25, -50.0, 19.5)
    )
    assert pixel_to_cm(640, 480, 640, 480, 34.5, 19.5, 50.0) == pytest.approx(
        (17.25, -50.0, 0.0)
    )


def test_calibrated_pixel_to_cm_uses_intrinsics_and_depth():
    camera_matrix = np.array(
        [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]
    )
    distortion = np.zeros(5)

    centre = pixel_to_cm_calibrated(
        320.0, 240.0, 50.0, camera_matrix, distortion, 19.5
    )
    offset = pixel_to_cm_calibrated(
        420.0, 140.0, 50.0, camera_matrix, distortion, 19.5
    )

    assert centre == pytest.approx((0.0, -50.0, 9.75), abs=1e-6)
    assert offset == pytest.approx((10.0, -50.0, 19.75), abs=1e-5)


@pytest.mark.parametrize(
    ("intersection", "expected_pixel"),
    [
        ((0.0, 0.0, 10.0), (960, 540)),
        ((-20.0, 0.0, 20.0), (0, 0)),
        ((20.0, 0.0, 0.0), (1919, 1079)),
    ],
)
def test_intersection_to_pixel_maps_centre_and_closed_panel_edges(
    intersection, expected_pixel
):
    assert intersection_to_pixel(intersection, 40.0, 20.0, 1920, 1080) == (
        expected_pixel
    )


@pytest.mark.parametrize(
    "intersection",
    [
        (-20.01, 0.0, 10.0),
        (20.01, 0.0, 10.0),
        (0.0, 0.0, -0.01),
        (0.0, 0.0, 20.01),
    ],
)
def test_intersection_to_pixel_rejects_points_outside_panel(intersection):
    assert intersection_to_pixel(intersection, 40.0, 20.0, 1920, 1080) is None


def test_estimate_ipd_depth_matches_pinhole_model_and_yaw_compensation():
    assert estimate_ipd_depth((0.0, 0.0), (63.0, 0.0), 500.0, 6.3) == pytest.approx(
        50.0
    )

    observed_foreshortened_ipd = 63.0 * np.cos(np.deg2rad(60.0))
    assert estimate_ipd_depth(
        (0.0, 0.0),
        (observed_foreshortened_ipd, 0.0),
        500.0,
        6.3,
        yaw_deg=60.0,
    ) == pytest.approx(50.0)


def test_estimate_ipd_depth_uses_safe_fallback_for_degenerate_observation():
    assert estimate_ipd_depth((10.0, 10.0), (10.5, 10.0), 500.0, 6.3) == 50.0
