# GlareTracker Documentation

This directory is organized by purpose. Start here instead of searching for the
newest-looking filename.

## Current sources of truth

Use these documents in this order:

1. [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) — current implementation status,
   limitations, and release state.
2. [`plans/VALIDATION_PLAN.md`](plans/VALIDATION_PLAN.md) — ordered validation stages,
   completion state, and evidence links.
3. [`plans/FUNCTIONAL_TEST_PLAN.md`](plans/FUNCTIONAL_TEST_PLAN.md) — concise operator
   checks for the current application.
4. [`guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md`](guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md)
   — detailed setup, operation, troubleshooting, and demonstration workflow.

If documentation disagrees with the source or automated tests, the source and tests
take precedence and the affected document should be corrected.

## Directory map

### `plans/`

- [`VALIDATION_PLAN.md`](plans/VALIDATION_PLAN.md) — active eight-stage research
  validation plan and completion record.
- [`FUNCTIONAL_TEST_PLAN.md`](plans/FUNCTIONAL_TEST_PLAN.md) — application-level
  pass/fail checklist.
- [`STEREO_CAMERA_BRINGUP_AND_UI_SIMPLIFICATION_PLAN.md`](plans/STEREO_CAMERA_BRINGUP_AND_UI_SIMPLIFICATION_PLAN.md)
  — proposed next development phase: guided individual/stereo calibration,
  post-filter verification, sparse light matching and interface reduction.

### `protocols/`

Controlled procedures for hardware-dependent research measurements:

- [`GROUND_TRUTH_MEASUREMENT_PROTOCOL.md`](protocols/GROUND_TRUTH_MEASUREMENT_PROTOCOL.md)
- [`TIMESTAMPED_RECORDING_SOAK_PROTOCOL.md`](protocols/TIMESTAMPED_RECORDING_SOAK_PROTOCOL.md)
- [`CAMERA_TO_WINDSHIELD_CALIBRATION_PROTOCOL.md`](protocols/CAMERA_TO_WINDSHIELD_CALIBRATION_PROTOCOL.md)
- [`PHYSICAL_INTERSECTION_TEST_PROTOCOL.md`](protocols/PHYSICAL_INTERSECTION_TEST_PROTOCOL.md)
- [`LATENCY_AND_RECOVERY_TEST_PROTOCOL.md`](protocols/LATENCY_AND_RECOVERY_TEST_PROTOCOL.md)
- [`PHYSICAL_LCD_VALIDATION_PROTOCOL.md`](protocols/PHYSICAL_LCD_VALIDATION_PROTOCOL.md)
- [`ENVIRONMENTAL_AND_VEHICLE_TEST_PROTOCOL.md`](protocols/ENVIRONMENTAL_AND_VEHICLE_TEST_PROTOCOL.md)

A protocol describes how to collect evidence; its existence does not mean that the
physical test has passed.

### `guides/`

- [`VISUAL_STEREO_CALIBRATION_GUIDE.md`](guides/VISUAL_STEREO_CALIBRATION_GUIDE.md) —
  illustrated flat-target, pose-coverage, stage-order, and success criteria for road
  stereo calibration.
- [`STEREO_CHESSBOARD_SETUP_GUIDE.md`](guides/STEREO_CHESSBOARD_SETUP_GUIDE.md) —
  current priority: mount, calibrate and tune the two road cameras.
- [`SYSTEM_WORKFLOW_AND_TEST_GUIDE.md`](guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md) —
  current operating and test workflow.

### `reference/`

- [`THESIS_AND_DESIGN_REFERENCE.md`](reference/THESIS_AND_DESIGN_REFERENCE.md) —
  long-form design history, rationale, algorithms, thesis material, and milestone
  context. It contains historical status snapshots; use `PROJECT_STATUS.md` and the
  validation plan for current status.

### `architecture/`

Generated architecture and technical-guide artifacts in HTML and PDF form. These are
reference exports and may lag behind the live source.

### `archive/`

Completed or superseded planning documents retained for decision history. Archived
documents are not active work queues.

## Naming rules

- Active work uses `*_PLAN.md`.
- Repeatable physical procedures use `*_PROTOCOL.md`.
- Operator instructions use `*_GUIDE.md`.
- Completed or superseded checklists go in `archive/`.
- Do not add `TEMP` or `TODO` filenames; update the active plan or archive the file.
