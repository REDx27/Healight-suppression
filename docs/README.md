# GlareTracker Documentation

This directory is organized by purpose. Start here instead of searching for the
newest-looking filename.

## Current sources of truth

Use these documents in this order:

1. [`reference/PROGRESS_MEETING_TECHNICAL_BRIEF.md`](reference/PROGRESS_MEETING_TECHNICAL_BRIEF.md)
   — current plain-language architecture, behaviour, rig/calibration plan, evidence,
   limitations, code map, and presentation material.
2. [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) — current implementation status,
   limitations, and release state.
3. [`plans/VALIDATION_PLAN.md`](plans/VALIDATION_PLAN.md) — ordered validation stages,
   completion state, and evidence links.
4. [`plans/FUNCTIONAL_TEST_PLAN.md`](plans/FUNCTIONAL_TEST_PLAN.md) — concise operator
   checks for the current application.
5. [`guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md`](guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md)
   — detailed setup, operation, troubleshooting, and demonstration workflow.

If documentation disagrees with the source or automated tests, the source and tests
take precedence and the affected document should be corrected.

## Directory map

### `plans/`

- [`CAMERA_LCD_AND_TOF_INTEGRATION_PLAN.md`](plans/CAMERA_LCD_AND_TOF_INTEGRATION_PLAN.md)
  - staged integration plan and implementation update: calibration UI, measured
    camera-to-LCD mapping and host ToF fusion are implemented; controller firmware
    and physical validation remain outstanding.
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

- [`DRIVER_AND_INSTALLED_RIG_CALIBRATION_GUIDE.md`](guides/DRIVER_AND_INSTALLED_RIG_CALIBRATION_GUIDE.md)
  - current mode-specific driver camera/ToF and final installed-rig workflow,
    independent skips, measured target conventions and explicit acceptance limits.
- [`VISUAL_STEREO_CALIBRATION_GUIDE.md`](guides/VISUAL_STEREO_CALIBRATION_GUIDE.md) —
  illustrated flat-target, pose-coverage, stage-order, and success criteria for road
  stereo calibration.
- [`STEREO_CHESSBOARD_SETUP_GUIDE.md`](guides/STEREO_CHESSBOARD_SETUP_GUIDE.md) —
  current priority: mount, calibrate and tune the two road cameras.
- [`SYSTEM_WORKFLOW_AND_TEST_GUIDE.md`](guides/SYSTEM_WORKFLOW_AND_TEST_GUIDE.md) —
  current operating and test workflow.

### `reference/`

- [`TOF_BRIDGE_PROTOCOL.md`](reference/TOF_BRIDGE_PROTOCOL.md) - exact USB packet,
  quality, identity, clock and recovery contract; firmware/hardware work is pending.
- [`PROGRESS_MEETING_TECHNICAL_BRIEF.md`](reference/PROGRESS_MEETING_TECHNICAL_BRIEF.md)
  — current shareable explanation for teammates, presentation preparation, and
  question-answering with another AI.
- [`THESIS_AND_DESIGN_REFERENCE.md`](reference/THESIS_AND_DESIGN_REFERENCE.md) —
  long-form design history, rationale, algorithms, thesis material, and milestone
  context. It contains historical status snapshots; use `PROJECT_STATUS.md` and the
  validation plan for current status.

### `architecture/`

Generated architecture and technical-guide artifacts in HTML and PDF form. These are
reference exports and may lag behind the live source.

### `Scripts_doc/`

- [`GlareTracker_Scripts_Code_Explanation.pdf`](Scripts_doc/GlareTracker_Scripts_Code_Explanation.pdf):
  33-page code-review study presentation covering every file in `scripts/`, its
  inputs, processing logic, outputs, limitations, and likely examiner questions.
  Reviewed against the local source on 2026-11-21.

### `GlareTracker_doc/`

- [`GlareTracker_Application_Code_Explanation.pdf`](GlareTracker_doc/GlareTracker_Application_Code_Explanation.pdf):
  49-page code-review study presentation covering all 30 Python files in
  `glare_tracker/`, including `widgets/`. Explains file responsibilities, inputs,
  processing, data handoffs, calibration, tracking, display output, worked examples,
  current implementation limits, and likely examiner questions. Reviewed against
  the local source on 2026-11-23.

The code-guide PDFs above are dated snapshots. They predate the installed calibration
and fixed/live driver-distance changes of 2026-11-24/25; use the current Markdown guides
and source for those additions.

### `archive/`

Completed or superseded planning documents retained for decision history. Archived
documents are not active work queues.

## Naming rules

- Active work uses `*_PLAN.md`.
- Repeatable physical procedures use `*_PROTOCOL.md`.
- Operator instructions use `*_GUIDE.md`.
- Completed or superseded checklists go in `archive/`.
- Do not add `TEMP` or `TODO` filenames; update the active plan or archive the file.
