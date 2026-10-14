# Camera-to-Windshield Extrinsic Calibration Protocol

This is the preparation and execution protocol for Stage 4 of the
[`Validation Plan`](../plans/VALIDATION_PLAN.md). Do not treat a low image reprojection error as proof of low
physical windshield error; independent physical validation targets are mandatory.

## Purpose

Estimate and store the installed rigid pose:

```text
p_windshield = R_camera_to_windshield * p_camera + t_camera_to_windshield
```

The saved profile is bound to the camera device, image size, intrinsic calibration,
and physical mount. Any change invalidates the profile.

## Prerequisites

1. Finish the Stage 2 ten-minute logging check.
2. Complete the relevant Stage 3 camera ground-truth baseline.
3. Fix the camera rigidly in its final mount.
4. Complete intrinsic calibration at the exact resolution and focus to be used.
5. Assign permanent, visible IDs to the camera and its mount.
6. Declare acceptance limits before fitting the pose.

Do not move, refocus, zoom, rotate, or change resolution after collecting targets.

## Coordinate frame

- Windshield plane: `Y = 0`.
- `X`: negative left, positive right.
- `Y`: negative toward the driver; positive toward the road.
- `Z`: zero at the windshield bottom; positive upward.
- Record the physical origin with photographs and a dimensioned drawing.

## Target layout

Use at least 11 accurately measured visible points distributed across the usable
windshield area:

- six or more **fit targets** spanning left/right, top/bottom, and centre;
- five or more separate **validation targets** not used by the fit;
- avoid collinear or tightly clustered points;
- include points near the declared operating boundary.

More well-distributed targets are preferred. Measure every target independently;
do not derive validation coordinates from the fitted camera model.

## Image observations

For each target, record its centre pixel `(u, v)` from an unscaled original camera
frame and its measured windshield coordinate `(X, 0, Z)` in centimetres. Preserve
the original image, timestamp, camera configuration, and point annotations.

The input JSON has this structure:

```json
{
  "camera": {
    "camera_index": 1,
    "image_size": [640, 480],
    "device_id": "physical-device-serial-or-stable-id",
    "mount_id": "road-mount-v1",
    "frame_name": "road_camera"
  },
  "intrinsics": {
    "camera_matrix": [[500, 0, 320], [0, 500, 240], [0, 0, 1]],
    "distortion": [0, 0, 0, 0, 0]
  },
  "acceptance": {
    "max_reprojection_rmse_px": 1.0,
    "max_validation_rmse_cm": 1.0,
    "max_validation_error_cm": 2.0
  },
  "fit_targets": [
    {"id": "FIT01", "windshield_cm": [-20, 0, 2], "image_px": [100, 400]}
  ],
  "validation_targets": [
    {"id": "VAL01", "windshield_cm": [-15, 0, 5], "image_px": [140, 360]}
  ]
}
```

The numeric limits above are examples, not approved project limits. Replace them
with justified values before collecting final data. The tool refuses input without
all three limits.

## Fit and validation

Run:

```powershell
py -3.13 scripts/calibrate_extrinsics.py calibration\road_targets.json `
  --profile calibration\road_camera_extrinsic.json `
  --report calibration\road_camera_extrinsic_report.json
```

The tool:

1. solves the installed pose using only `fit_targets`;
2. reports fit-target reprojection error in pixels;
3. projects each held-out validation pixel ray onto physical `Y = 0`;
4. compares those intersections with independently measured targets in centimetres;
5. records mean, RMSE, p95, maximum, and axis errors;
6. writes the profile only if every predeclared limit passes.

A failed calibration still writes its report and must remain in the research archive.

## Profile validity checks

Before applying a profile, require exact matches for:

- camera index and stable device identity;
- resolution;
- intrinsic-calibration fingerprint;
- mount ID;
- profile format version.

Reject the profile and remove blocker output if any check fails. Recalibrate after
camera/mount movement, focus or zoom changes, resolution changes, windshield/panel
movement, or physical impact.

## Repeatability and remount test

1. Collect and fit three complete target sets without moving the rig.
2. Compare rotation, translation, held-out RMSE, and maximum error.
3. Remove and reinstall the camera mount.
4. Confirm the old mount ID/profile is rejected.
5. Recalibrate and repeat the held-out target set.
6. Report within-installation repeatability separately from remounting error.

## Required evidence

- intrinsic profile and its fingerprint;
- input JSON and unscaled annotated frames;
- dimensioned target map and setup photographs;
- passing or failing report for every attempt;
- saved profile only for passing attempts;
- repeatability/remount results;
- exact software commit and application configuration.

Stage 4 remains incomplete until physical held-out targets meet the declared
centimetre-error limits. Passing synthetic unit tests proves only the mathematics
and guardrails, not the installed-camera accuracy.
