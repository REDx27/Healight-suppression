"""Measured calibration records and conversions shared by dialogs and live vision.

All reconstruction uses native OpenCV pixels/camera axes. Installed coordinates
use the LCD bottom-centre frame: X lateral, Y roadward, Z upward, in cm.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from glare_tracker.calibration import CalibrationResult, _calibration_dir
from glare_tracker.extrinsics import RigidTransform3D, solve_pnp_camera_to_windshield


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def camera_record(result, index):
    if not np.isfinite(result.rms_error) or not 0 <= result.rms_error <= 1.5:
        raise ValueError("Camera intrinsic RMS must pass the 1.5 px fit limit")
    matrix = np.asarray(result.camera_matrix, float)
    dist = np.asarray(result.dist_coeffs, float)
    if (matrix.shape != (3, 3) or not np.isfinite(matrix).all()
            or not np.isfinite(dist).all() or min(matrix[0, 0], matrix[1, 1]) <= 0
            or dist.size not in (4, 5, 8, 12, 14)
            or len(result.image_size) != 2 or min(result.image_size) <= 0
            or not np.allclose(matrix[2], [0, 0, 1])):
        raise ValueError("Invalid native camera model")
    return {"camera_index": int(index), "image_size": list(result.image_size),
            "camera_matrix": matrix.tolist(), "distortion": dist.tolist(),
            "rms_px": float(result.rms_error), "pixel_convention": "native_unmirrored"}


def camera_model(record):
    result = CalibrationResult(np.asarray(record["camera_matrix"], float),
                               np.asarray(record["distortion"], float),
                               tuple(record["image_size"]), float(record["rms_px"]))
    camera_record(result, record["camera_index"])
    if record.get("pixel_convention") != "native_unmirrored":
        raise ValueError("Unsupported driver pixel convention")
    return result


def stereo_signature(profile):
    if profile is None:
        return ""
    return signature({"indices": profile.camera_indices,
                      "size": profile.cam1.image_size,
                      **{key: np.asarray(getattr(profile, key)).tolist()
                         for key in ("R", "T", "R1", "R2", "P1", "P2")},
                      "K1": profile.cam1.camera_matrix.tolist(),
                      "D1": profile.cam1.dist_coeffs.tolist(),
                      "K2": profile.cam2.camera_matrix.tolist(),
                      "D2": profile.cam2.dist_coeffs.tolist()})


class CalibrationStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else _calibration_dir() / "installation"

    def load(self, name):
        path = self.directory / f"{name}.json"
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("version") != 1 or value.get("kind") != name:
            raise ValueError(f"Unsupported {name} profile")
        payload = value["data"]
        if signature(payload) != value.get("fingerprint"):
            raise ValueError(f"Corrupt {name} profile")
        return payload

    def save(self, name, payload):
        # Atomic activation: an unsuccessful attempt never destroys the old profile.
        self.directory.mkdir(parents=True, exist_ok=True)
        value = {"version": 1, "kind": name, "data": payload,
                 "fingerprint": signature(payload),
                 "saved_utc": datetime.now(timezone.utc).isoformat()}
        path = self.directory / f"{name}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(path)
        return path


def board_points(pattern, square_cm, origin, angles_deg, side="road"):
    """Known board pose; origin is the marked FIRST INNER corner, not paper edge."""
    if not 0 < float(square_cm) < 100 or not np.isfinite(square_cm):
        raise ValueError("Measure a finite positive square size")
    if side not in ("road", "driver"):
        raise ValueError("Unknown installed camera side")
    local = np.zeros((pattern[0] * pattern[1], 3), float)
    local[:, :2] = np.mgrid[0:pattern[0], 0:pattern[1]].T.reshape(-1, 2) * square_cm
    origin, angles = np.asarray(origin, float), np.deg2rad(angles_deg)
    if origin.shape != (3,) or angles.shape != (3,) or not np.isfinite([origin, angles]).all():
        raise ValueError("Board pose must contain finite XYZ and rotation values")
    ax, ay, az = angles
    rx = np.array([[1, 0, 0], [0, np.cos(ax), -np.sin(ax)], [0, np.sin(ax), np.cos(ax)]])
    ry = np.array([[np.cos(ay), 0, np.sin(ay)], [0, 1, 0], [-np.sin(ay), 0, np.cos(ay)]])
    rz = np.array([[np.cos(az), -np.sin(az), 0], [np.sin(az), np.cos(az), 0], [0, 0, 1]])
    base = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
    if side == "driver":
        base = np.diag([-1., -1., 1.]) @ base
    rotation = rz @ ry @ rx @ base
    return local @ rotation.T + origin


def fit_installed_pose(samples, model, side, max_px=1.5, max_cm=2.0):
    fit = [s for s in samples if s["split"] == "fit"]
    validation = [s for s in samples if s["split"] == "validation"]
    if len(fit) < 6 or len(validation) < 3:
        raise ValueError("Capture six measured fit placements and three different validation placements")
    keys = [tuple(s["pose_key"]) for s in samples]
    if len(set(keys)) != len(keys):
        raise ValueError("Fit and validation must use different measured placements")
    if len({round(float(s["pose_key"][1]), 2) for s in fit}) < 3:
        raise ValueError("Fit placements must span at least three measured Y distances")
    points = np.concatenate([s["points_cm"] for s in fit])
    pixels = np.concatenate([s["pixels"] for s in fit]).reshape(-1, 2)
    result = solve_pnp_camera_to_windshield(points, pixels, model.camera_matrix,
                                          model.dist_coeffs, camera_frame=side)
    inverse = result.transform.inverse()
    truth = np.concatenate([s["points_cm"] for s in validation])
    observed = np.concatenate([s["pixels"] for s in validation]).reshape(-1, 2)
    camera_truth = np.asarray(inverse.apply(truth))
    if np.any(camera_truth[:, 2] <= 0) or (side == "road" and np.any(truth[:, 1] <= 0)) or (
            side == "driver" and np.any(truth[:, 1] >= 0)):
        raise ValueError("Targets must be in front of the camera and on the correct side of the LCD")
    normalized = cv2.undistortPoints(observed.reshape(-1, 1, 2), model.camera_matrix,
                                     model.dist_coeffs).reshape(-1, 2)
    rays = np.column_stack((normalized, np.ones(len(normalized))))
    rays /= np.linalg.norm(rays, axis=1)[:, None]
    residual_cm = np.linalg.norm(np.cross(camera_truth, rays), axis=1)
    rvec, _ = cv2.Rodrigues(inverse.rotation)
    predicted, _ = cv2.projectPoints(truth, rvec, inverse.translation_cm,
                                      model.camera_matrix, model.dist_coeffs)
    errors = np.linalg.norm(predicted.reshape(-1, 2) - observed, axis=1)
    report = {"fit_rmse_px": result.reprojection_metrics.rmse_px,
              "held_out_rmse_px": float(np.sqrt(np.mean(errors ** 2))),
              "held_out_p95_transverse_cm": float(np.percentile(residual_cm, 95)),
              "held_out_max_transverse_cm": float(max(residual_cm)),
              "limits": {"max_rmse_px": max_px, "max_transverse_cm": max_cm},
              "note": "Transverse ray agreement; independently validate stereo/eye depth and final spots."}
    report["passed"] = bool(result.reprojection_metrics.rmse_px <= max_px
                            and report["held_out_rmse_px"] <= max_px
                            and max(residual_cm) <= max_cm)
    if not report["passed"]:
        raise ValueError("Installed pose failed held-out limits: " + json.dumps(report))
    return {"transform": result.transform.to_dict(), "report": report}


def fit_panel_mapping(samples, width_cm, height_cm, max_error_cm=0.3):
    fit = [s for s in samples if s["split"] == "fit"]
    validation = [s for s in samples if s["split"] == "validation"]
    if len(fit) < 6 or len(validation) < 3:
        raise ValueError("Measure six fit marks and three separate validation marks")
    uv = [tuple(s["uv"]) for s in samples]
    if len(set(uv)) != len(uv):
        raise ValueError("Use separate fit and validation pixels")
    design = np.array([[*s["uv"], 1.] for s in fit])
    positions = np.array([s["xz_cm"] for s in fit])
    if not np.isfinite([*design.ravel(), *positions.ravel()]).all() or np.linalg.matrix_rank(design) < 3:
        raise ValueError("Panel marks must be finite and span two dimensions")
    matrix = np.linalg.lstsq(design, positions, rcond=None)[0].T
    homogeneous = np.vstack((matrix, [0, 0, 1]))
    if abs(np.linalg.det(homogeneous)) < 1e-9:
        raise ValueError("Panel mapping is singular")
    ideal = np.array([[width_cm, 0, -width_cm / 2], [0, -height_cm, height_cm]])
    if np.max(np.abs(matrix - ideal)) > max(1., max_error_cm * 3):
        raise ValueError("Panel marks disagree with the selected active-area dimensions/orientation")
    errors = [np.linalg.norm(matrix @ [*s["uv"], 1.] - s["xz_cm"]) for s in validation]
    if not np.isfinite(errors).all() or max(errors) > max_error_cm:
        raise ValueError("Held-out LCD marks exceed the declared physical mapping limit")
    return {"xz_to_uv": np.linalg.inv(homogeneous)[:2].tolist(),
            "max_error_cm": float(max(errors)), "limit_cm": max_error_cm,
            "width_cm": width_cm, "height_cm": height_cm}


def fit_tof(samples, device_id, sensor_z_cm=0., eye_offset_cm=0., max_error_cm=2.):
    fit = [s for s in samples if s["split"] == "fit"]
    validation = [s for s in samples if s["split"] == "validation"]
    if len(fit) < 3 or len(validation) < 2 or not device_id.strip():
        raise ValueError("Use three fit distances, two held-out distances and a sensor ID")
    distances = [float(s["reference_cm"]) for s in samples]
    if (not np.isfinite(distances).all() or len(set(distances)) != len(distances)
            or min(distances) < 5 or max(distances) > 150):
        raise ValueError("Use distinct reference distances in the 5-150 cm bench range")
    for s in samples:
        raw = np.asarray(s["raw_cm"], float)
        if len(raw) < 20 or not np.isfinite(raw).all() or np.std(raw) > 1.:
            raise ValueError("Each distance needs 20 stable valid readings (standard deviation <= 1 cm)")
    bias = float(np.median([s["reference_cm"] - np.median(s["raw_cm"]) for s in fit]))
    errors = [abs(np.median(s["raw_cm"]) + bias - s["reference_cm"]) for s in validation]
    if max(errors) > max_error_cm or not np.isfinite([bias, sensor_z_cm, eye_offset_cm]).all():
        raise ValueError("ToF held-out range errors or measured offsets are invalid")
    return {"device_id": device_id.strip(), "bias_cm": bias,
            "sensor_z_cm": float(sensor_z_cm), "eye_offset_cm": float(eye_offset_cm),
            "min_cm": min(distances), "max_cm": max(distances),
            "held_out_max_error_cm": float(max(errors)), "limit_cm": max_error_cm,
            "mount_assumption": "near_coaxial_parallel", "maximum_pose_deg": 10.,
            "note": "Rigid-target range fit; facial eye-depth/target association still needs physical validation."}


def validate_tof_profile(profile):
    """Fail closed on incomplete/mismatched saved sensor calibration records."""
    keys = ("bias_cm", "sensor_z_cm", "eye_offset_cm", "min_cm", "max_cm",
            "held_out_max_error_cm", "limit_cm", "maximum_pose_deg")
    if (not profile.get("device_id", "").strip()
            or profile.get("mount_assumption") != "near_coaxial_parallel"
            or not np.isfinite([profile[k] for k in keys]).all()
            or not 5 <= profile["min_cm"] < profile["max_cm"] <= 150
            or not 0 <= profile["held_out_max_error_cm"] <= profile["limit_cm"] <= 2
            or not 0 < profile["maximum_pose_deg"] <= 10):
        raise ValueError("Invalid ToF calibration record")
    return profile


def frontal_pose(pitch, yaw, maximum_deg=10.):
    # The generic face model has Y upwards and Z out of the face; a frontal
    # OpenCV camera therefore estimates about +/-180 degrees around X.
    pitch_error = min(abs(pitch), abs(180. - abs(pitch)))
    return bool(np.isfinite([pitch, yaw]).all()
                and max(pitch_error, abs(yaw)) <= maximum_deg)


def unproject_eye(pixel, depth_cm, model):
    point = np.asarray(pixel, float).reshape(1, 1, 2)
    normalized = cv2.undistortPoints(point, model.camera_matrix, model.dist_coeffs)[0, 0]
    if not np.isfinite(depth_cm) or depth_cm <= 0:
        raise ValueError("Eye depth must be finite and positive")
    return np.array([*normalized, 1.]) * depth_cm


def triangulate_lcd(left, right, stereo, installed):
    homogeneous = cv2.triangulatePoints(stereo.P1, stereo.P2,
                                         np.asarray(left, float).reshape(2, 1),
                                         np.asarray(right, float).reshape(2, 1))[:, 0]
    if not np.isfinite(homogeneous).all() or abs(homogeneous[3]) < 1e-9:
        return None
    rectified = homogeneous[:3] / homogeneous[3]
    raw = stereo.R1.T @ rectified
    right_raw = stereo.R @ raw + np.asarray(stereo.T).reshape(3)
    if raw[2] <= 0 or right_raw[2] <= 0:
        return None
    return RigidTransform3D.from_dict(installed["transform"]).apply(raw)


def rig_compatibility_errors(rig, setup, use_driver, use_road):
    if rig is None:
        return ["Installed rig calibration is missing"]
    errors = []
    binding = rig.get("binding", {})
    if binding.get("panel_cm") != setup["panel_cm"]:
        errors.append("Panel dimensions changed")
    if binding.get("display") != setup.get("display"):
        errors.append("Selected LCD identity or display mode changed")
    for role, needed, keys in (("driver", use_driver, ("driver_index", "driver_fingerprint")),
                               ("road", use_road, ("road_indices", "stereo_fingerprint"))):
        if not needed:
            continue
        if any(not setup.get(key) and key.endswith("fingerprint") for key in keys):
            errors.append(f"{role.title()} component calibration is missing")
        if any(binding.get(key) != setup.get(key) for key in keys):
            errors.append(f"{role.title()} camera selection/calibration changed")
        try:
            pose = rig["poses"][role]
            transform = RigidTransform3D.from_dict(pose["transform"])
            if not pose["report"]["passed"] or transform.from_frame != role or transform.to_frame != "windshield":
                raise ValueError("Pose not accepted")
        except (KeyError, ValueError, TypeError):
            errors.append(f"{role.title()} installed pose is missing or invalid")
    try:
        matrix = np.asarray(rig["panel"]["xz_to_uv"], float)
        if matrix.shape != (2, 3) or not np.isfinite(matrix).all():
            raise ValueError("Invalid panel mapping")
    except (KeyError, ValueError, TypeError):
        errors.append("Physical LCD mapping is missing or invalid")
    return errors
