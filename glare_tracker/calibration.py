"""Camera calibration utilities — single camera and stereo pair.

Provides interactive calibration using a checkerboard pattern, and
functions to load/save calibration data.  Calibration results are
stored as NumPy ``.npz`` files in the ``calibration/`` directory.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


# ── Default checkerboard parameters ─────────────────────────────────

DEFAULT_PATTERN_SIZE = (9, 6)  # inner corners (cols, rows)
DEFAULT_SQUARE_SIZE_CM = 2.5   # physical size of each square


@dataclass
class CalibrationResult:
    """Holds intrinsic calibration data for a single camera."""

    camera_matrix: np.ndarray          # 3×3 intrinsic matrix K
    dist_coeffs: np.ndarray            # distortion coefficients
    image_size: tuple[int, int]        # (width, height)
    rms_error: float = 0.0             # reprojection RMS error (pixels)
    focal_length_px: float = 0.0       # fx (horizontal focal length in pixels)
    principal_point: tuple[float, float] = (0.0, 0.0)  # (cx, cy)

    def __post_init__(self):
        self.focal_length_px = float(self.camera_matrix[0, 0])
        self.principal_point = (
            float(self.camera_matrix[0, 2]),
            float(self.camera_matrix[1, 2]),
        )


@dataclass
class StereoCalibrationResult:
    """Holds stereo calibration data for a camera pair."""

    cam1: CalibrationResult
    cam2: CalibrationResult
    R: np.ndarray                      # rotation between cameras
    T: np.ndarray                      # translation between cameras (cm)
    E: np.ndarray                      # essential matrix
    F: np.ndarray                      # fundamental matrix
    R1: np.ndarray                     # rectification rotation cam1
    R2: np.ndarray                     # rectification rotation cam2
    P1: np.ndarray                     # rectified projection cam1
    P2: np.ndarray                     # rectified projection cam2
    Q: np.ndarray                      # disparity-to-depth mapping
    baseline_cm: float = 0.0           # physical baseline distance
    rms_error: float = 0.0
    camera_indices: tuple[int, int] | None = None

    def __post_init__(self):
        f = float(self.P1[0, 0])
        if f > 0:
            self.baseline_cm = abs(float(self.P2[0, 3])) / f


@dataclass
class DriverDepthCalibration:
    """One-point monocular driver-depth calibration for demonstrations."""

    ipd_cm: float
    reference_distance_cm: float
    reference_ipd_px: float
    focal_length_px: float
    image_size: tuple[int, int]
    camera_index: int

    def as_intrinsic_calibration(self) -> CalibrationResult:
        """Create a zero-distortion intrinsic approximation from the scale."""
        width, height = self.image_size
        camera_matrix = np.array([
            [self.focal_length_px, 0.0, width / 2.0],
            [0.0, self.focal_length_px, height / 2.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)
        return CalibrationResult(
            camera_matrix=camera_matrix,
            dist_coeffs=np.zeros((5, 1), dtype=np.float64),
            image_size=self.image_size,
            rms_error=-1.0,
        )


@dataclass
class MonocularRangeCalibration:
    """Reference-size range model for one road-facing camera.

    ``range_scale_cm_px`` is the product of known reference distance and the
    observed bright-blob diameter.  Live range is estimated as scale/diameter.
    This is suitable for a controlled demonstration using the same lamp and
    exposure conditions, not for measurement-grade ranging.
    """

    reference_distance_cm: float
    reference_diameter_px: float
    range_scale_cm_px: float
    image_size: tuple[int, int]
    camera_index: int
    brightness_threshold: int = 210

    def estimate_distance_cm(self, diameter_px: float) -> float:
        diameter = max(1.0, float(diameter_px))
        return float(self.range_scale_cm_px / diameter)


# ── Calibration file I/O ────────────────────────────────────────────

def _calibration_dir() -> Path:
    """Return the calibration data directory (project_root/calibration/)."""
    project_root = Path(__file__).resolve().parent.parent
    cal_dir = project_root / "calibration"
    cal_dir.mkdir(exist_ok=True)
    return cal_dir


def save_single_calibration(result: CalibrationResult, name: str = "driver_cam"):
    """Save single-camera calibration to a .npz file."""
    path = _calibration_dir() / f"{name}_calib.npz"
    np.savez(
        str(path),
        camera_matrix=result.camera_matrix,
        dist_coeffs=result.dist_coeffs,
        image_size=np.array(result.image_size),
        rms_error=np.array([result.rms_error]),
    )
    return path


def load_single_calibration(name: str = "driver_cam") -> Optional[CalibrationResult]:
    """Load single-camera calibration from a .npz file, or None if missing."""
    path = _calibration_dir() / f"{name}_calib.npz"
    if not path.exists():
        return None
    with np.load(str(path)) as data:
        return CalibrationResult(
            camera_matrix=data["camera_matrix"],
            dist_coeffs=data["dist_coeffs"],
            image_size=tuple(data["image_size"].tolist()),
            rms_error=float(data["rms_error"][0]),
        )


def save_driver_depth_calibration(
    result: DriverDepthCalibration, name: str = "driver_depth",
):
    """Save a guided one-point driver depth profile."""
    path = _calibration_dir() / f"{name}_calib.npz"
    np.savez(
        str(path),
        ipd_cm=np.array([result.ipd_cm]),
        reference_distance_cm=np.array([result.reference_distance_cm]),
        reference_ipd_px=np.array([result.reference_ipd_px]),
        focal_length_px=np.array([result.focal_length_px]),
        image_size=np.array(result.image_size),
        camera_index=np.array([result.camera_index]),
    )
    return path


def load_driver_depth_calibration(
    name: str = "driver_depth",
) -> Optional[DriverDepthCalibration]:
    """Load a guided driver depth profile, if present."""
    path = _calibration_dir() / f"{name}_calib.npz"
    if not path.exists():
        return None
    with np.load(str(path)) as data:
        camera_index = int(data["camera_index"][0]) if "camera_index" in data.files else 0
        return DriverDepthCalibration(
            ipd_cm=float(data["ipd_cm"][0]),
            reference_distance_cm=float(data["reference_distance_cm"][0]),
            reference_ipd_px=float(data["reference_ipd_px"][0]),
            focal_length_px=float(data["focal_length_px"][0]),
            image_size=tuple(int(value) for value in data["image_size"].tolist()),
            camera_index=camera_index,
        )


def save_monocular_range_calibration(
    result: MonocularRangeCalibration, name: str = "road_range",
):
    """Save a one-point apparent-size road range profile."""
    path = _calibration_dir() / f"{name}_calib.npz"
    np.savez(
        str(path),
        reference_distance_cm=np.array([result.reference_distance_cm]),
        reference_diameter_px=np.array([result.reference_diameter_px]),
        range_scale_cm_px=np.array([result.range_scale_cm_px]),
        image_size=np.array(result.image_size),
        camera_index=np.array([result.camera_index]),
        brightness_threshold=np.array([result.brightness_threshold]),
    )
    return path


def load_monocular_range_calibration(
    name: str = "road_range",
) -> Optional[MonocularRangeCalibration]:
    """Load a one-point road range profile, if present."""
    path = _calibration_dir() / f"{name}_calib.npz"
    if not path.exists():
        return None
    with np.load(str(path)) as data:
        camera_index = int(data["camera_index"][0]) if "camera_index" in data.files else 1
        threshold = int(data["brightness_threshold"][0]) if "brightness_threshold" in data.files else 210
        return MonocularRangeCalibration(
            reference_distance_cm=float(data["reference_distance_cm"][0]),
            reference_diameter_px=float(data["reference_diameter_px"][0]),
            range_scale_cm_px=float(data["range_scale_cm_px"][0]),
            image_size=tuple(int(value) for value in data["image_size"].tolist()),
            camera_index=camera_index,
            brightness_threshold=threshold,
        )


def save_stereo_calibration(result: StereoCalibrationResult, name: str = "stereo"):
    """Save stereo calibration to a .npz file."""
    path = _calibration_dir() / f"{name}_calib.npz"
    np.savez(
        str(path),
        mtx1=result.cam1.camera_matrix, dist1=result.cam1.dist_coeffs,
        mtx2=result.cam2.camera_matrix, dist2=result.cam2.dist_coeffs,
        image_size=np.array(result.cam1.image_size),
        R=result.R, T=result.T, E=result.E, F=result.F,
        R1=result.R1, R2=result.R2, P1=result.P1, P2=result.P2, Q=result.Q,
        rms_error=np.array([result.rms_error]),
        camera_indices=np.array(result.camera_indices or (-1, -1)),
    )
    return path


def load_stereo_calibration(name: str = "stereo") -> Optional[StereoCalibrationResult]:
    """Load stereo calibration from a .npz file, or None if missing."""
    path = _calibration_dir() / f"{name}_calib.npz"
    if not path.exists():
        return None
    with np.load(str(path)) as d:
        cam1 = CalibrationResult(d["mtx1"], d["dist1"], tuple(d["image_size"].tolist()))
        cam2 = CalibrationResult(d["mtx2"], d["dist2"], tuple(d["image_size"].tolist()))
        return StereoCalibrationResult(
            cam1=cam1, cam2=cam2,
            R=d["R"], T=d["T"], E=d["E"], F=d["F"],
            R1=d["R1"], R2=d["R2"], P1=d["P1"], P2=d["P2"], Q=d["Q"],
            rms_error=float(d["rms_error"][0]),
            camera_indices=(tuple(int(v) for v in d["camera_indices"])
                            if "camera_indices" in d else None),
        )


def stereo_profile_name(primary: int, secondary: int) -> str:
    """Camera order is part of a stereo calibration, not interchangeable."""
    return f"stereo_{int(primary)}_{int(secondary)}"


def stereo_profile_compatible(result, primary, secondary, image_size):
    """Reject mismatched or invalid profiles before producing metric observations."""
    if result is None:
        return False
    matrices = (result.R, result.T, result.R1, result.R2, result.P1, result.P2,
                result.Q, result.cam1.camera_matrix, result.cam2.camera_matrix,
                result.cam1.dist_coeffs, result.cam2.dist_coeffs)
    return bool(
        result is not None
        and primary != secondary
        and result.camera_indices == (primary, secondary)
        and tuple(result.cam1.image_size) == tuple(image_size)
        and tuple(result.cam2.image_size) == tuple(image_size)
        and all(np.isfinite(matrix).all() for matrix in matrices)
        and 0 <= result.rms_error <= 1.5
        and np.isfinite(result.baseline_cm) and result.baseline_cm > 0
        and result.P1[0, 0] > 0 and result.P1[1, 1] > 0
        and result.P2[0, 3] < 0
    )


# ── Checkerboard detection helpers ──────────────────────────────────

def _build_object_points(
    pattern_size: tuple[int, int] = DEFAULT_PATTERN_SIZE,
    square_size_cm: float = DEFAULT_SQUARE_SIZE_CM,
) -> np.ndarray:
    """Build the 3D object points for a planar checkerboard (Z=0)."""
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size_cm
    return objp


_SUBPIX_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)


def detect_checkerboard(
    frame: np.ndarray,
    pattern_size: tuple[int, int] = DEFAULT_PATTERN_SIZE,
) -> Optional[np.ndarray]:
    """Detect checkerboard corners with sub-pixel refinement.

    Returns refined corner array (N, 1, 2) or None.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    if hasattr(cv2, "findChessboardCornersSB"):
        flags = cv2.CALIB_CB_NORMALIZE_IMAGE
        flags |= getattr(cv2, "CALIB_CB_EXHAUSTIVE", 0)
        flags |= getattr(cv2, "CALIB_CB_ACCURACY", 0)
        try:
            found, corners = cv2.findChessboardCornersSB(
                gray, pattern_size, flags=flags)
            if found:
                return corners.astype(np.float32)
        except cv2.error:
            pass

    # Retain the classic detector as a compatibility fallback for older
    # OpenCV builds and frames where the sector-based search does not finish.
    found, corners = cv2.findChessboardCorners(
        gray, pattern_size,
        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK,
    )
    if not found:
        return None
    return cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), _SUBPIX_CRITERIA)


def draw_checkerboard(
    frame: np.ndarray,
    corners: np.ndarray,
    pattern_size: tuple[int, int] = DEFAULT_PATTERN_SIZE,
) -> np.ndarray:
    """Draw detected checkerboard corners on a frame (in-place)."""
    cv2.drawChessboardCorners(frame, pattern_size, corners, True)
    return frame


# ── Single camera calibration ──────────────────────────────────────

def calibrate_single(
    frames: list[np.ndarray],
    pattern_size: tuple[int, int] = DEFAULT_PATTERN_SIZE,
    square_size_cm: float = DEFAULT_SQUARE_SIZE_CM,
) -> Optional[CalibrationResult]:
    """Run single-camera calibration from a list of frames.

    Each frame should contain a visible checkerboard.
    Returns CalibrationResult or None if insufficient detections.
    """
    objp = _build_object_points(pattern_size, square_size_cm)
    obj_points: list[np.ndarray] = []
    img_points: list[np.ndarray] = []
    img_size: Optional[tuple[int, int]] = None

    for frame in frames:
        h, w = frame.shape[:2]
        img_size = (w, h)
        corners = detect_checkerboard(frame, pattern_size)
        if corners is not None:
            obj_points.append(objp)
            img_points.append(corners)

    if len(obj_points) < 8:
        return None  # need at least 8 good detections

    rms, mtx, dist, _, _ = cv2.calibrateCamera(
        obj_points, img_points, img_size, None, None,
    )
    return CalibrationResult(
        camera_matrix=mtx,
        dist_coeffs=dist,
        image_size=img_size,
        rms_error=rms,
    )


# ── Stereo calibration ─────────────────────────────────────────────

def calibrate_stereo(
    frames_cam1: list[np.ndarray],
    frames_cam2: list[np.ndarray],
    pattern_size: tuple[int, int] = DEFAULT_PATTERN_SIZE,
    square_size_cm: float = DEFAULT_SQUARE_SIZE_CM,
) -> Optional[StereoCalibrationResult]:
    """Run stereo calibration from paired views of a stationary chessboard.

    Returns StereoCalibrationResult or None if insufficient detections.
    """
    if len(frames_cam1) != len(frames_cam2):
        raise ValueError("Stereo samples must contain the same number of paired frames")
    if not np.isfinite(square_size_cm) or square_size_cm <= 0:
        raise ValueError("Measured square size must be positive and finite")
    if len(pattern_size) != 2 or any(int(v) != v or v < 3 for v in pattern_size):
        raise ValueError("Specify at least 3 inner corners in each direction")
    sizes = {frame.shape[:2] for frame in frames_cam1 + frames_cam2}
    if len(sizes) > 1:
        raise ValueError("Both cameras and every sample must have the same resolution")
    objp = _build_object_points(pattern_size, square_size_cm)
    obj_points: list[np.ndarray] = []
    img_points1: list[np.ndarray] = []
    img_points2: list[np.ndarray] = []
    img_size: Optional[tuple[int, int]] = None

    for f1, f2 in zip(frames_cam1, frames_cam2):
        h, w = f1.shape[:2]
        img_size = (w, h)
        c1 = detect_checkerboard(f1, pattern_size)
        c2 = detect_checkerboard(f2, pattern_size)
        if c1 is not None and c2 is not None:
            obj_points.append(objp)
            img_points1.append(c1)
            img_points2.append(c2)

    if len(obj_points) < 8:
        return None

    # Individual calibrations first
    rms1, mtx1, dist1, _, _ = cv2.calibrateCamera(
        obj_points, img_points1, img_size, None, None,
    )
    rms2, mtx2, dist2, _, _ = cv2.calibrateCamera(
        obj_points, img_points2, img_size, None, None,
    )

    # Stereo calibration — fix intrinsics to avoid divergence
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
    rms_s, mtx1, dist1, mtx2, dist2, R, T, E, F = cv2.stereoCalibrate(
        obj_points, img_points1, img_points2,
        mtx1, dist1, mtx2, dist2,
        img_size, criteria=criteria, flags=cv2.CALIB_FIX_INTRINSIC,
    )

    # Rectification
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
        mtx1, dist1, mtx2, dist2, img_size, R, T,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0,
    )

    cam1 = CalibrationResult(mtx1, dist1, img_size, rms1)
    cam2 = CalibrationResult(mtx2, dist2, img_size, rms2)

    return StereoCalibrationResult(
        cam1=cam1, cam2=cam2,
        R=R, T=T, E=E, F=F,
        R1=R1, R2=R2, P1=P1, P2=P2, Q=Q,
        rms_error=rms_s,
    )


# ── Coordinate helpers ──────────────────────────────────────────────

def calibrate_stereo_with_intrinsics(
    frames_cam1: list[np.ndarray],
    frames_cam2: list[np.ndarray],
    cam1: CalibrationResult,
    cam2: CalibrationResult,
    pattern_size: tuple[int, int] = DEFAULT_PATTERN_SIZE,
    square_size_cm: float = DEFAULT_SQUARE_SIZE_CM,
) -> Optional[StereoCalibrationResult]:
    """Fit stereo geometry while holding explicit LEFT/RIGHT intrinsics fixed."""
    if len(frames_cam1) != len(frames_cam2):
        raise ValueError("Stereo samples must contain the same number of paired frames")
    if not np.isfinite(square_size_cm) or square_size_cm <= 0:
        raise ValueError("Measured square size must be positive and finite")
    if len(pattern_size) != 2 or any(int(v) != v or v < 3 for v in pattern_size):
        raise ValueError("Specify at least 3 inner corners in each direction")
    sizes = {frame.shape[:2] for frame in frames_cam1 + frames_cam2}
    if len(sizes) > 1:
        raise ValueError("Both cameras and every sample must have the same resolution")
    if not frames_cam1:
        return None
    image_size = (frames_cam1[0].shape[1], frames_cam1[0].shape[0])
    if cam1.image_size != image_size or cam2.image_size != image_size:
        raise ValueError("Individual calibrations must match the stereo capture resolution")

    object_template = _build_object_points(pattern_size, square_size_cm)
    object_points, image_points1, image_points2 = [], [], []
    for left, right in zip(frames_cam1, frames_cam2):
        corners1 = detect_checkerboard(left, pattern_size)
        corners2 = detect_checkerboard(right, pattern_size)
        if corners1 is not None and corners2 is not None:
            object_points.append(object_template)
            image_points1.append(corners1)
            image_points2.append(corners2)
    if len(object_points) < 8:
        return None

    matrix1, distortion1 = cam1.camera_matrix.copy(), cam1.dist_coeffs.copy()
    matrix2, distortion2 = cam2.camera_matrix.copy(), cam2.dist_coeffs.copy()
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
    rms, matrix1, distortion1, matrix2, distortion2, rotation, translation, essential, fundamental = cv2.stereoCalibrate(
        object_points, image_points1, image_points2,
        matrix1, distortion1, matrix2, distortion2,
        image_size, criteria=criteria, flags=cv2.CALIB_FIX_INTRINSIC,
    )
    rect1, rect2, projection1, projection2, disparity_map, _, _ = cv2.stereoRectify(
        matrix1, distortion1, matrix2, distortion2, image_size, rotation, translation,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0,
    )
    return StereoCalibrationResult(
        cam1=CalibrationResult(matrix1, distortion1, image_size, cam1.rms_error),
        cam2=CalibrationResult(matrix2, distortion2, image_size, cam2.rms_error),
        R=rotation, T=translation, E=essential, F=fundamental,
        R1=rect1, R2=rect2, P1=projection1, P2=projection2, Q=disparity_map,
        rms_error=rms,
    )


def undistort_point(
    u: float, v: float, calib: CalibrationResult,
) -> tuple[float, float]:
    """Undistort a single pixel coordinate, returning corrected (u, v)."""
    pt = np.array([[[u, v]]], dtype=np.float32)
    norm = cv2.undistortPoints(pt, calib.camera_matrix, calib.dist_coeffs, P=calib.camera_matrix)
    return float(norm[0, 0, 0]), float(norm[0, 0, 1])


def pixel_to_3d(
    u: float, v: float, depth_cm: float, calib: CalibrationResult,
) -> tuple[float, float, float]:
    """Unproject a pixel + depth into 3D camera-space coordinates (cm).

    Uses calibrated intrinsics with lens distortion correction.
    """
    pt = np.array([[[u, v]]], dtype=np.float32)
    norm = cv2.undistortPoints(pt, calib.camera_matrix, calib.dist_coeffs)
    x_norm = float(norm[0, 0, 0])
    y_norm = float(norm[0, 0, 1])
    return (x_norm * depth_cm, y_norm * depth_cm, depth_cm)


def estimate_focal_length_from_fov(
    image_width_px: int, hfov_degrees: float,
) -> float:
    """Estimate focal length (pixels) from known horizontal FOV."""
    return (image_width_px / 2.0) / np.tan(np.deg2rad(hfov_degrees / 2.0))
