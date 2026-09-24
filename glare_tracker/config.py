"""Shared configuration and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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
    camera_z_cm: float = 19.5       # top-centre of default windshield
    ipd_cm: float = 6.3            # inter-pupillary distance (human avg)
    use_calibration: bool = False   # whether to use camera calibration data
