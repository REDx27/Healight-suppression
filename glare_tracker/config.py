"""Shared configuration and constants."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrackingConfig:
    """Immutable snapshot of tracking parameters passed to the camera thread.

    All distances are in centimetres.
    """
    screen_w_cm: float = 34.5
    screen_h_cm: float = 19.5
    eye_dist_cm: float = 50.0
    camera_x_cm: float = 0.0
    camera_y_cm: float = 0.0
    camera_z_cm: float = 30.0
