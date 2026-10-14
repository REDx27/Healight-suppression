"""Fit and validate one installed camera-to-windshield pose from JSON targets.

The output profile is written only when every predeclared acceptance limit passes.
The report is always written so failed calibrations remain auditable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glare_tracker.extrinsics import (
    CameraExtrinsicProfile,
    evaluate_transform,
    intrinsic_fingerprint,
    project_pixel_to_windshield_plane,
    RigidTransform3D,
    save_extrinsic_profile,
    solve_pnp_camera_to_windshield,
)


def _targets(data, key, minimum):
    targets = data.get(key, [])
    if len(targets) < minimum:
        raise ValueError(f"{key} requires at least {minimum} targets")
    identifiers = [str(target.get("id", "")) for target in targets]
    if any(not identifier for identifier in identifiers):
        raise ValueError(f"Every {key} target requires a non-empty id")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{key} target ids must be unique")
    windshield = np.asarray(
        [target["windshield_cm"] for target in targets], dtype=np.float64
    )
    image = np.asarray([target["image_px"] for target in targets], dtype=np.float64)
    if windshield.shape != (len(targets), 3):
        raise ValueError(f"{key} windshield_cm values must contain X, Y, Z")
    if image.shape != (len(targets), 2):
        raise ValueError(f"{key} image_px values must contain u, v")
    return targets, windshield, image


def calibrate_from_file(
    input_path: Path,
    profile_path: Path,
    report_path: Path,
):
    data = json.loads(input_path.read_text(encoding="utf-8"))
    metadata = data["camera"]
    intrinsics = data["intrinsics"]
    acceptance = data["acceptance"]
    required_limits = (
        "max_reprojection_rmse_px",
        "max_validation_rmse_cm",
        "max_validation_error_cm",
    )
    missing_limits = [key for key in required_limits if key not in acceptance]
    if missing_limits:
        raise ValueError(
            "Acceptance limits must be declared before calibration: "
            + ", ".join(missing_limits)
        )

    fit_targets, fit_windshield, fit_image = _targets(data, "fit_targets", 6)
    validation_targets, validation_windshield, validation_image = _targets(
        data, "validation_targets", 5
    )
    camera_matrix = np.asarray(intrinsics["camera_matrix"], dtype=np.float64)
    distortion = np.asarray(intrinsics["distortion"], dtype=np.float64)
    result = solve_pnp_camera_to_windshield(
        fit_windshield,
        fit_image,
        camera_matrix,
        distortion,
        camera_frame=str(metadata["frame_name"]),
    )

    predicted_validation = []
    validation_rows = []
    for target, truth, image_point in zip(
        validation_targets, validation_windshield, validation_image
    ):
        predicted = project_pixel_to_windshield_plane(
            image_point,
            camera_matrix,
            distortion,
            result.transform,
        )
        if predicted is None:
            raise ValueError(
                f"Validation ray for {target['id']} does not reach windshield Y=0"
            )
        predicted_validation.append(predicted)
        error_cm = float(np.linalg.norm(np.asarray(predicted) - truth))
        validation_rows.append(
            {
                "id": target["id"],
                "image_px": [float(value) for value in image_point],
                "windshield_cm": [float(value) for value in truth],
                "predicted_windshield_cm": [float(value) for value in predicted],
                "error_cm": error_cm,
            }
        )

    validation_metrics = evaluate_transform(
        RigidTransform3D.identity("windshield"),
        np.asarray(predicted_validation),
        validation_windshield,
    )
    checks = {
        "reprojection_rmse_px": (
            result.reprojection_metrics.rmse_px
            <= float(acceptance["max_reprojection_rmse_px"])
        ),
        "validation_rmse_cm": (
            validation_metrics.rmse_cm
            <= float(acceptance["max_validation_rmse_cm"])
        ),
        "validation_max_error_cm": (
            validation_metrics.max_error_cm
            <= float(acceptance["max_validation_error_cm"])
        ),
    }
    passed = all(checks.values())
    fingerprint = intrinsic_fingerprint(camera_matrix, distortion)
    profile = CameraExtrinsicProfile(
        transform=result.transform,
        camera_index=int(metadata["camera_index"]),
        image_size=tuple(int(value) for value in metadata["image_size"]),
        device_id=str(metadata["device_id"]),
        mount_id=str(metadata["mount_id"]),
        intrinsic_fingerprint=fingerprint,
        fit_metrics=validation_metrics,
        calibration_point_count=len(fit_targets),
        fit_method="solve_pnp",
        reprojection_metrics=result.reprojection_metrics,
    )

    report = {
        "status": "PASS" if passed else "FAIL",
        "input_file": str(input_path),
        "profile_written": bool(passed),
        "acceptance": acceptance,
        "checks": checks,
        "intrinsic_fingerprint": fingerprint,
        "fit_target_count": len(fit_targets),
        "validation_target_count": len(validation_targets),
        "reprojection_metrics": result.reprojection_metrics.to_dict(),
        "validation_metrics": validation_metrics.to_dict(),
        "transform": result.transform.to_dict(),
        "validation_targets": validation_rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    if passed:
        save_extrinsic_profile(profile, profile_path)
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Fit and validate a camera-to-windshield extrinsic profile"
    )
    parser.add_argument("input_json", type=Path)
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("calibration/camera_extrinsic.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("calibration/camera_extrinsic_report.json"),
    )
    args = parser.parse_args()
    report = calibrate_from_file(args.input_json, args.profile, args.report)
    print(f"Extrinsic calibration: {report['status']}")
    print(args.report)
    if report["status"] == "PASS":
        print(args.profile)
    raise SystemExit(0 if report["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
