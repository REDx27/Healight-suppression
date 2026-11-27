"""Read-only calibrated camera poses for the centimetre-based scene.

This module provides display data only. It does not alter calibration records,
live observations, tracking configuration, or physical output authorization.
"""

from dataclasses import dataclass

import numpy as np

from glare_tracker.extrinsics import RigidTransform3D
from glare_tracker.installation import rig_compatibility_errors


@dataclass(frozen=True)
class SceneCameraPose:
    role: str
    camera_index: int
    center_cm: tuple[float, float, float]
    rotation: tuple[tuple[float, float, float], ...]

    @classmethod
    def from_transform(cls, role, index, transform):
        return cls(role, int(index), tuple(float(v) for v in transform.translation_cm),
                   tuple(tuple(float(v) for v in row) for row in transform.rotation))


def installed_camera_scene_poses(rig, setup, stereo=None):
    """Return compatible, accepted camera poses in the panel's world frame.

    The saved road transform maps the *raw LEFT* camera into the panel frame.
    OpenCV stereo uses p_right = R p_left + T. Invert that transform, then
    compose it with the saved LEFT pose to locate/orient RIGHT. Rectification
    projections and disparity baselines are not camera-to-panel poses.
    """
    if not isinstance(rig, dict) or not isinstance(setup, dict):
        return ()
    poses = []
    try:
        if not rig_compatibility_errors(rig, setup, True, False):
            driver = RigidTransform3D.from_dict(rig["poses"]["driver"]["transform"])
            poses.append(SceneCameraPose.from_transform("driver", setup["driver_index"], driver))
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    try:
        if stereo is not None and not rig_compatibility_errors(rig, setup, False, True):
            indices = tuple(setup["road_indices"])
            if tuple(stereo.camera_indices or ()) != indices or len(indices) != 2 or indices[0] == indices[1]:
                return tuple(poses)
            left = RigidTransform3D.from_dict(rig["poses"]["road"]["transform"])
            left_to_right = RigidTransform3D(stereo.R, np.asarray(stereo.T).reshape(3),
                                             "road", "road_right")
            if np.linalg.norm(left_to_right.translation_cm) <= 0:
                return tuple(poses)
            right = left_to_right.inverse().then(left)
            poses.extend((SceneCameraPose.from_transform("road_left", indices[0], left),
                          SceneCameraPose.from_transform("road_right", indices[1], right)))
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    return tuple(poses)
