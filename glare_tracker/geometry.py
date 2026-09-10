"""Pure geometry helpers — no Qt or UI dependencies.

The windshield sits in the vertical X-Z plane at Y = 0.
X is lateral, Y is depth (front/back), Z is vertical height.
The driver sits behind the windshield at negative Y.
"""


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
        eye→light segment.
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
    """
    x_cm = (eye_x_px - frame_w / 2) / frame_w * screen_w_cm
    y_cm = -eye_dist_cm
    z_cm = (frame_h / 2 - eye_y_px) / frame_h * screen_h_cm + screen_h_cm / 2
    return (x_cm, y_cm, z_cm)
