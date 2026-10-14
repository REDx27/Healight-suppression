# End-to-End Physical Intersection Test Protocol

This protocol is Stage 5 of the
[`Validation Plan`](../plans/VALIDATION_PLAN.md). It must use extrinsic profiles
that passed Stage 4 held-out physical validation.

## Objective

For independently measured eye and light positions, verify that the application
places the calculated point on the physical windshield where the true eye-to-light
line crosses `Y = 0`.

The analysis keeps six error categories separate:

1. eye-position input error;
2. light-position input error;
3. physical target-marking/reference error;
4. input-error propagation at the windshield;
5. geometry implementation error;
6. total application-to-physical end-to-end error.

## Safety

- Use a stationary laboratory rig and a diffused, eye-safe lamp.
- Never conduct this test in moving traffic or on a public road.
- Do not place an observer's eye on a high-intensity direct beam.
- A mannequin/optical eye target is preferred for initial validation.

## Prerequisites

- Stage 2 logging soak test passed.
- Stage 3 driver and light measurements completed.
- Stage 4 driver and road-camera profiles passed and remain compatible.
- Windshield origin, axes, usable boundary, and target grid are physically marked.
- Acceptance limits are written before final trials.

## Test matrix

Use at least 30 independently positioned eye/light pairs, including:

- both eyes separately and the midpoint compatibility mode;
- centre, left/right, upper/lower windshield regions;
- near, nominal, and far driver distances;
- near, medium, and far controlled-light distances;
- head roll producing vertically separated left/right intersections;
- at least two simultaneous light locations, analyzed as separate eye/light rays;
- in-bounds and deliberately out-of-bounds intersections.

Repeat at least three complete setups after physically repositioning the targets.

## Measurements per eye/light ray

Record these values in centimetres:

- `measured_eye_cm`: independently measured eye target position;
- `estimated_eye_cm`: camera/tracker estimate;
- `measured_light_cm`: independently measured lamp position;
- `estimated_light_cm`: camera/tracker estimate;
- `physical_intersection_cm`: independently marked ray crossing on the windshield;
- `application_intersection_cm`: application output for the same synchronized sample.

Use unique trial, eye, and light IDs. Preserve the diagnostics session, timestamp,
video frame, configuration, extrinsic-profile hashes, setup photograph, and operator
notes for every trial.

## Physical reference

Use a taut low-stretch line or alignment laser between the measured optical eye
target and diffused lamp centre. Mark its windshield crossing without allowing the
line, camera, windshield, or target mounts to move. Record the target uncertainty.

The analysis script independently recomputes the mathematical crossing from measured
eye/light coordinates. A disagreement between that reference and the physical mark
is reported as physical-mark error instead of being hidden in application error.

## Input file and analysis

Create a JSON file containing predeclared limits and trial records:

```json
{
  "acceptance": {
    "minimum_trials": 30,
    "max_geometry_rmse_cm": 0.1,
    "max_end_to_end_rmse_cm": 1.0,
    "max_end_to_end_error_cm": 2.0
  },
  "trials": [
    {
      "id": "T001",
      "eye_id": "E1",
      "light_id": "L1",
      "measured_eye_cm": [-3, -50, 10],
      "estimated_eye_cm": [-3.1, -50.5, 10.1],
      "measured_light_cm": [6, 100, 10],
      "estimated_light_cm": [6.2, 101, 10.1],
      "physical_intersection_cm": [0, 0, 10],
      "application_intersection_cm": [0.2, 0, 10.1]
    }
  ]
}
```

The displayed limits are examples only. Replace them with justified project limits.

Run:

```powershell
py -3.13 scripts/analyze_physical_intersections.py trials.json `
  --report-json intersection_validation_report.json `
  --report-csv intersection_validation_trials.csv
```

Review every failed/outlier trial against its synchronized video and setup record.
Do not delete raw failures. If an exclusion is justified, preserve both original and
excluded summaries and state the predeclared exclusion rule.

## Exit evidence

- complete input JSON and raw diagnostics;
- passing/failing JSON and CSV reports;
- physical setup drawing and photographs;
- uncertainty statement for eye, lamp, and physical intersection measurements;
- separate error results for each eye, light, distance, and windshield region;
- explicit failures, exclusions, and limitations.

Stage 5 remains incomplete until the physical matrix satisfies its predeclared
end-to-end limits.
