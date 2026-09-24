"""Pure geometry helpers -- no Qt or UI dependencies.

The windshield sits in the vertical X-Z plane at Y = 0.
X is lateral, Y is depth (front/back), Z is vertical height.
The driver sits behind the windshield at negative Y.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


def compute_intersection(eye_cm, light_cm):
    """Compute where the ray from *eye_cm* toward *light_cm* crosses Y = 0.

    Parameters
    ----------
    eye_cm : tuple[float, float, float]
        Eye position (x, y, z) in cm.  Y should be negative (behind windshield).
    light_cm : tuple[float, float, float]
        Light-source position in cm.  Y should be positive (in front).

    Returns
    -------
    tuple[float, float, float] | None
        ``(x, 0.0, z)`` intersection point, or ``None`` when the ray is
        parallel to the plane or the intersection falls outside the
        eye->light segment.
    """
    x1, y1, z1 = eye_cm
    x2, y2, z2 = light_cm
    dy = y2 - y1
    if abs(dy) < 1e-9:
        return None
    t = -y1 / dy
    if not 0.0 <= t <= 1.0:
        return None
    return (x1 + t * (x2 - x1), 0.0, z1 + t * (z2 - z1))


def pixel_to_cm(eye_x_px, eye_y_px, frame_w, frame_h,
                screen_w_cm, screen_h_cm, eye_dist_cm):
    """Convert pixel-space iris midpoint to approximate real-world cm.

    The windshield is the vertical X-Z plane at Y = 0.
    The driver sits behind it at ``Y = -eye_dist_cm``.

    .. note:: This is the **uncalibrated** fallback.  When camera
       calibration data is available, use ``pixel_to_cm_calibrated()``
       instead for accurate lens-corrected positioning.
    """
    x_cm = (eye_x_px - frame_w / 2) / frame_w * screen_w_cm
    y_cm = -eye_dist_cm
    z_cm = (frame_h / 2 - eye_y_px) / frame_h * screen_h_cm + screen_h_cm / 2
    return (x_cm, y_cm, z_cm)


def pixel_to_cm_calibrated(
    u: float,
    v: float,
    depth_cm: float,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    screen_h_cm: float,
) -> tuple[float, float, float]:
    """Convert pixel coordinate to real-world cm using calibrated camera intrinsics.

    Uses ``cv2.undistortPoints`` to correct for lens distortion, then
    unprojects using the pinhole model at the given depth.

    Coordinate system: X=lateral, Y=-depth (behind windshield), Z=height.
    """
    import cv2

    pt = np.array([[[u, v]]], dtype=np.float32)
    norm = cv2.undistortPoints(pt, camera_matrix, dist_coeffs)
    x_norm = float(norm[0, 0, 0])
    y_norm = float(norm[0, 0, 1])

    x_cm = x_norm * depth_cm
    y_cm = -depth_cm
    z_cm = -y_norm * depth_cm + screen_h_cm / 2
    return (x_cm, y_cm, z_cm)


def intersection_to_pixel(
    intersection_cm: tuple[float, float, float],
    panel_w_cm: float,
    panel_h_cm: float,
    panel_res_x: int,
    panel_res_y: int,
) -> tuple[int, int] | None:
    """Map a 3D intersection point on the windshield (Y=0) to LCD pixel coordinates.

    Parameters
    ----------
    intersection_cm : (x, 0.0, z)
        Intersection point in world coordinates.
    panel_w_cm, panel_h_cm : float
        Physical dimensions of the LCD panel.
    panel_res_x, panel_res_y : int
        LCD resolution in pixels.

    Returns
    -------
    (px, py) pixel coordinates, or None if out of bounds.
    """
    ix, _, iz = intersection_cm
    hw = panel_w_cm / 2.0

    # Convert from world coords to panel-local coords
    x_local = ix + hw             # 0..panel_w_cm (left to right)
    z_local = panel_h_cm - iz     # 0..panel_h_cm (top to bottom)

    if not (0 <= x_local <= panel_w_cm) or not (0 <= z_local <= panel_h_cm):
        return None

    px = int(x_local / panel_w_cm * panel_res_x)
    py = int(z_local / panel_h_cm * panel_res_y)
    return (px, py)


def estimate_ipd_depth(
    left_iris_px: tuple[float, float],
    right_iris_px: tuple[float, float],
    focal_length_px: float,
    ipd_real_cm: float = 6.3,
    yaw_deg: float = 0.0,
) -> float:
    """Estimate the driver's distance from the camera using IPD.

    Uses the pinhole model: ``Z = (IPD_real * f) / IPD_pixels``.
    Compensates for head yaw (turning) which foreshortens the apparent IPD.

    Returns depth in centimetres.
    """
    dx = left_iris_px[0] - right_iris_px[0]
    dy = left_iris_px[1] - right_iris_px[1]
    ipd_pixels = np.sqrt(dx * dx + dy * dy)

    if ipd_pixels < 1.0:
        return 50.0  # fallback

    # Compensate for head yaw foreshortening
    cos_yaw = np.cos(np.deg2rad(abs(yaw_deg)))
    if cos_yaw > 0.3:
        ipd_pixels /= cos_yaw

    return (ipd_real_cm * focal_length_px) / ipd_pixels
