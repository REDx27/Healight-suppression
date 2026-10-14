"""Rigid camera-to-windshield coordinate transforms and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import cv2


def _as_points(values, *, name: str) -> np.ndarray:
    points = np.asarray(values, dtype=np.float64)
    if points.ndim == 1:
        if points.shape != (3,):
            raise ValueError(f"{name} must contain three coordinates")
    elif points.ndim == 2:
        if points.shape[1] != 3:
            raise ValueError(f"{name} must have shape (N, 3)")
    else:
        raise ValueError(f"{name} must be a 3-vector or an (N, 3) array")
    if not np.all(np.isfinite(points)):
        raise ValueError(f"{name} contains a non-finite value")
    return points


@dataclass(frozen=True)
class RigidTransform3D:
    """A proper rigid transform from one named 3D frame to another."""

    rotation: np.ndarray
    translation_cm: np.ndarray
    from_frame: str = "camera"
    to_frame: str = "windshield"

    def __post_init__(self):
        rotation = np.asarray(self.rotation, dtype=np.float64)
        translation = np.asarray(self.translation_cm, dtype=np.float64).reshape(-1)
        if rotation.shape != (3, 3):
            raise ValueError("Rotation must have shape (3, 3)")
        if translation.shape != (3,):
            raise ValueError("Translation must contain three coordinates")
        if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
            raise ValueError("Transform contains a non-finite value")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6):
            raise ValueError("Rotation must be orthonormal")
        if not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-6):
            raise ValueError("Rotation must be proper with determinant +1")
        if not self.from_frame or not self.to_frame:
            raise ValueError("Transform frame names must be non-empty")
        object.__setattr__(self, "rotation", rotation.copy())
        object.__setattr__(self, "translation_cm", translation.copy())

    @classmethod
    def identity(cls, frame: str = "camera") -> "RigidTransform3D":
        return cls(np.eye(3), np.zeros(3), frame, frame)

    def apply(self, points_cm):
        """Transform one 3-vector or an array of row-vector points."""

        points = _as_points(points_cm, name="points_cm")
        if points.ndim == 1:
            transformed = self.rotation @ points + self.translation_cm
            return tuple(float(value) for value in transformed)
        return points @ self.rotation.T + self.translation_cm

    def inverse(self) -> "RigidTransform3D":
        inverse_rotation = self.rotation.T
        return RigidTransform3D(
            inverse_rotation,
            -(inverse_rotation @ self.translation_cm),
            self.to_frame,
            self.from_frame,
        )

    def then(self, next_transform: "RigidTransform3D") -> "RigidTransform3D":
        """Compose this A->B transform with a supplied B->C transform."""

        if self.to_frame != next_transform.from_frame:
            raise ValueError(
                f"Cannot compose {self.from_frame}->{self.to_frame} with "
                f"{next_transform.from_frame}->{next_transform.to_frame}"
            )
        return RigidTransform3D(
            next_transform.rotation @ self.rotation,
            next_transform.rotation @ self.translation_cm
            + next_transform.translation_cm,
            self.from_frame,
            next_transform.to_frame,
        )

    def to_dict(self) -> dict:
        return {
            "from_frame": self.from_frame,
            "to_frame": self.to_frame,
            "rotation": self.rotation.tolist(),
            "translation_cm": self.translation_cm.tolist(),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "RigidTransform3D":
        return cls(
            rotation=data["rotation"],
            translation_cm=data["translation_cm"],
            from_frame=str(data["from_frame"]),
            to_frame=str(data["to_frame"]),
        )


@dataclass(frozen=True)
class TransformErrorMetrics:
    point_count: int
    mean_error_cm: float
    rmse_cm: float
    p95_error_cm: float
    max_error_cm: float
    axis_bias_cm: tuple[float, float, float]
    axis_rmse_cm: tuple[float, float, float]

    def to_dict(self) -> dict:
        return {
            "point_count": self.point_count,
            "mean_error_cm": self.mean_error_cm,
            "rmse_cm": self.rmse_cm,
            "p95_error_cm": self.p95_error_cm,
            "max_error_cm": self.max_error_cm,
            "axis_bias_cm": list(self.axis_bias_cm),
            "axis_rmse_cm": list(self.axis_rmse_cm),
        }


@dataclass(frozen=True)
class ReprojectionErrorMetrics:
    point_count: int
    mean_error_px: float
    rmse_px: float
    p95_error_px: float
    max_error_px: float

    def to_dict(self) -> dict:
        return {
            "point_count": self.point_count,
            "mean_error_px": self.mean_error_px,
            "rmse_px": self.rmse_px,
            "p95_error_px": self.p95_error_px,
            "max_error_px": self.max_error_px,
        }


@dataclass(frozen=True)
class PnPExtrinsicResult:
    transform: RigidTransform3D
    reprojection_metrics: ReprojectionErrorMetrics
    projected_points_px: np.ndarray


def solve_pnp_camera_to_windshield(
    windshield_points_cm,
    image_points_px,
    camera_matrix,
    distortion,
    *,
    camera_frame: str = "camera",
) -> PnPExtrinsicResult:
    """Estimate installed camera pose from known windshield-frame targets.

    OpenCV returns the windshield->camera pose.  This helper inverts that pose
    so callers receive the camera->windshield transform used by the tracker.
    """

    object_points = _as_points(
        windshield_points_cm, name="windshield_points_cm"
    )
    image_points = np.asarray(image_points_px, dtype=np.float64)
    matrix = np.asarray(camera_matrix, dtype=np.float64)
    coefficients = np.asarray(distortion, dtype=np.float64)
    if object_points.ndim != 2 or len(object_points) < 4:
        raise ValueError("At least four windshield target points are required")
    if image_points.shape != (len(object_points), 2):
        raise ValueError("Image points must have shape (N, 2) matching targets")
    if matrix.shape != (3, 3):
        raise ValueError("Camera matrix must have shape (3, 3)")
    if not np.all(np.isfinite(image_points)):
        raise ValueError("Image points contain a non-finite value")
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(coefficients)):
        raise ValueError("Camera intrinsics contain a non-finite value")
    if np.linalg.matrix_rank(object_points - np.mean(object_points, axis=0)) < 2:
        raise ValueError("Windshield target points must not be collinear")

    success, rotation_vector, translation_vector = cv2.solvePnP(
        object_points,
        image_points,
        matrix,
        coefficients,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        raise ValueError("OpenCV could not solve the installed camera pose")
    windshield_to_camera_rotation, _ = cv2.Rodrigues(rotation_vector)
    camera_to_windshield_rotation = windshield_to_camera_rotation.T
    camera_to_windshield_translation = -(
        camera_to_windshield_rotation @ translation_vector.reshape(3)
    )
    transform = RigidTransform3D(
        camera_to_windshield_rotation,
        camera_to_windshield_translation,
        camera_frame,
        "windshield",
    )

    projected, _ = cv2.projectPoints(
        object_points,
        rotation_vector,
        translation_vector,
        matrix,
        coefficients,
    )
    projected = projected.reshape(-1, 2)
    errors = np.linalg.norm(projected - image_points, axis=1)
    metrics = ReprojectionErrorMetrics(
        point_count=len(errors),
        mean_error_px=float(np.mean(errors)),
        rmse_px=float(np.sqrt(np.mean(np.square(errors)))),
        p95_error_px=float(np.percentile(errors, 95)),
        max_error_px=float(np.max(errors)),
    )
    return PnPExtrinsicResult(transform, metrics, projected)


def project_pixel_to_windshield_plane(
    image_point_px: Sequence[float],
    camera_matrix,
    distortion,
    camera_to_windshield: RigidTransform3D,
) -> tuple[float, float, float] | None:
    """Intersect an undistorted camera ray with the windshield plane ``Y=0``."""

    point = np.asarray(image_point_px, dtype=np.float64).reshape(-1)
    if point.shape != (2,) or not np.all(np.isfinite(point)):
        raise ValueError("Image point must contain two finite coordinates")
    matrix = np.asarray(camera_matrix, dtype=np.float64)
    coefficients = np.asarray(distortion, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError("Camera matrix must have shape (3, 3)")
    normalized = cv2.undistortPoints(
        point.reshape(1, 1, 2), matrix, coefficients
    )[0, 0]
    camera_ray = np.array([normalized[0], normalized[1], 1.0])
    windshield_ray = camera_to_windshield.rotation @ camera_ray
    origin = camera_to_windshield.translation_cm
    if abs(windshield_ray[1]) < 1e-12:
        return None
    distance = -origin[1] / windshield_ray[1]
    if distance < 0:
        return None
    intersection = origin + distance * windshield_ray
    intersection[1] = 0.0
    return tuple(float(value) for value in intersection)


def evaluate_transform(
    transform: RigidTransform3D,
    source_points_cm,
    target_points_cm,
) -> TransformErrorMetrics:
    source = _as_points(source_points_cm, name="source_points_cm")
    target = _as_points(target_points_cm, name="target_points_cm")
    if source.ndim != 2 or target.ndim != 2 or source.shape != target.shape:
        raise ValueError("Source and target points must have matching (N, 3) shapes")
    if len(source) == 0:
        raise ValueError("At least one validation point is required")
    residuals = transform.apply(source) - target
    distances = np.linalg.norm(residuals, axis=1)
    axis_bias = np.mean(residuals, axis=0)
    axis_rmse = np.sqrt(np.mean(np.square(residuals), axis=0))
    return TransformErrorMetrics(
        point_count=len(source),
        mean_error_cm=float(np.mean(distances)),
        rmse_cm=float(np.sqrt(np.mean(np.square(distances)))),
        p95_error_cm=float(np.percentile(distances, 95)),
        max_error_cm=float(np.max(distances)),
        axis_bias_cm=tuple(float(value) for value in axis_bias),
        axis_rmse_cm=tuple(float(value) for value in axis_rmse),
    )


def fit_rigid_transform(
    source_points_cm,
    target_points_cm,
    *,
    from_frame: str = "camera",
    to_frame: str = "windshield",
) -> RigidTransform3D:
    """Fit a least-squares proper rigid transform using the Kabsch algorithm."""

    source = _as_points(source_points_cm, name="source_points_cm")
    target = _as_points(target_points_cm, name="target_points_cm")
    if source.ndim != 2 or target.ndim != 2 or source.shape != target.shape:
        raise ValueError("Source and target points must have matching (N, 3) shapes")
    if len(source) < 3:
        raise ValueError("At least three point correspondences are required")
    source_centered = source - np.mean(source, axis=0)
    target_centered = target - np.mean(target, axis=0)
    if np.linalg.matrix_rank(source_centered) < 2:
        raise ValueError("Calibration points must not be collinear")

    covariance = source_centered.T @ target_centered
    left, _, right_t = np.linalg.svd(covariance)
    rotation = right_t.T @ left.T
    if np.linalg.det(rotation) < 0:
        right_t[-1, :] *= -1
        rotation = right_t.T @ left.T
    translation = np.mean(target, axis=0) - rotation @ np.mean(source, axis=0)
    return RigidTransform3D(
        rotation,
        translation,
        from_frame=from_frame,
        to_frame=to_frame,
    )


def intrinsic_fingerprint(camera_matrix, distortion) -> str:
    """Return a stable fingerprint for the intrinsic calibration arrays."""

    digest = hashlib.sha256()
    for value in (camera_matrix, distortion):
        array = np.asarray(value, dtype=np.float64)
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


@dataclass(frozen=True)
class CameraExtrinsicProfile:
    """Installed camera pose plus identity and fit-quality metadata."""

    transform: RigidTransform3D
    camera_index: int
    image_size: tuple[int, int]
    device_id: str
    mount_id: str
    intrinsic_fingerprint: str
    fit_metrics: TransformErrorMetrics
    calibration_point_count: int
    fit_method: str = "3d_correspondence"
    reprojection_metrics: ReprojectionErrorMetrics | None = None
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="microseconds"
        )
    )
    profile_version: int = 1

    def __post_init__(self):
        if self.transform.to_frame != "windshield":
            raise ValueError("Extrinsic profile must transform into windshield frame")
        width, height = self.image_size
        if int(width) <= 0 or int(height) <= 0:
            raise ValueError("Image dimensions must be positive")
        if not self.device_id.strip() or not self.mount_id.strip():
            raise ValueError("Device and mount identifiers are required")
        if len(self.intrinsic_fingerprint) != 64:
            raise ValueError("Intrinsic fingerprint must be a SHA-256 hex digest")
        try:
            int(self.intrinsic_fingerprint, 16)
        except ValueError as error:
            raise ValueError("Intrinsic fingerprint is not hexadecimal") from error
        if self.calibration_point_count < 3:
            raise ValueError("At least three calibration points are required")
        if self.fit_method not in {"3d_correspondence", "solve_pnp"}:
            raise ValueError("Unsupported extrinsic fit method")

    def compatibility_errors(
        self,
        *,
        camera_index: int,
        image_size: tuple[int, int],
        device_id: str,
        mount_id: str,
        intrinsic_fingerprint: str,
    ) -> tuple[str, ...]:
        checks = (
            (self.camera_index == int(camera_index), "camera index changed"),
            (self.image_size == tuple(image_size), "image size changed"),
            (self.device_id == device_id, "camera device changed"),
            (self.mount_id == mount_id, "camera mount changed"),
            (
                self.intrinsic_fingerprint == intrinsic_fingerprint,
                "intrinsic calibration changed",
            ),
        )
        return tuple(message for valid, message in checks if not valid)

    def to_dict(self) -> dict:
        return {
            "profile_version": self.profile_version,
            "created_utc": self.created_utc,
            "camera_index": self.camera_index,
            "image_size": list(self.image_size),
            "device_id": self.device_id,
            "mount_id": self.mount_id,
            "intrinsic_fingerprint": self.intrinsic_fingerprint,
            "calibration_point_count": self.calibration_point_count,
            "fit_method": self.fit_method,
            "fit_metrics": self.fit_metrics.to_dict(),
            "reprojection_metrics": (
                None
                if self.reprojection_metrics is None
                else self.reprojection_metrics.to_dict()
            ),
            "transform": self.transform.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> "CameraExtrinsicProfile":
        if int(data.get("profile_version", 0)) != 1:
            raise ValueError("Unsupported extrinsic profile version")
        metrics = data["fit_metrics"]
        reprojection = data.get("reprojection_metrics")
        return cls(
            transform=RigidTransform3D.from_dict(data["transform"]),
            camera_index=int(data["camera_index"]),
            image_size=tuple(int(value) for value in data["image_size"]),
            device_id=str(data["device_id"]),
            mount_id=str(data["mount_id"]),
            intrinsic_fingerprint=str(data["intrinsic_fingerprint"]),
            calibration_point_count=int(data["calibration_point_count"]),
            fit_metrics=TransformErrorMetrics(
                point_count=int(metrics["point_count"]),
                mean_error_cm=float(metrics["mean_error_cm"]),
                rmse_cm=float(metrics["rmse_cm"]),
                p95_error_cm=float(metrics["p95_error_cm"]),
                max_error_cm=float(metrics["max_error_cm"]),
                axis_bias_cm=tuple(float(value) for value in metrics["axis_bias_cm"]),
                axis_rmse_cm=tuple(float(value) for value in metrics["axis_rmse_cm"]),
            ),
            fit_method=str(data.get("fit_method", "3d_correspondence")),
            reprojection_metrics=(
                None
                if reprojection is None
                else ReprojectionErrorMetrics(
                    point_count=int(reprojection["point_count"]),
                    mean_error_px=float(reprojection["mean_error_px"]),
                    rmse_px=float(reprojection["rmse_px"]),
                    p95_error_px=float(reprojection["p95_error_px"]),
                    max_error_px=float(reprojection["max_error_px"]),
                )
            ),
            created_utc=str(data["created_utc"]),
            profile_version=1,
        )


def build_extrinsic_profile(
    source_points_cm,
    windshield_points_cm,
    *,
    camera_index: int,
    image_size: tuple[int, int],
    device_id: str,
    mount_id: str,
    intrinsic_fingerprint: str,
    from_frame: str = "camera",
) -> CameraExtrinsicProfile:
    transform = fit_rigid_transform(
        source_points_cm,
        windshield_points_cm,
        from_frame=from_frame,
        to_frame="windshield",
    )
    metrics = evaluate_transform(
        transform, source_points_cm, windshield_points_cm
    )
    return CameraExtrinsicProfile(
        transform=transform,
        camera_index=int(camera_index),
        image_size=tuple(int(value) for value in image_size),
        device_id=device_id,
        mount_id=mount_id,
        intrinsic_fingerprint=intrinsic_fingerprint,
        fit_metrics=metrics,
        calibration_point_count=len(source_points_cm),
    )


def save_extrinsic_profile(
    profile: CameraExtrinsicProfile, path: str | Path
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(profile.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(destination)
    return destination


def load_extrinsic_profile(path: str | Path) -> CameraExtrinsicProfile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return CameraExtrinsicProfile.from_dict(data)
