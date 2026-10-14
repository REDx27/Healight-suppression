# Physical LCD Validation Protocol

This is Stage 7 of the
[`Validation Plan`](../plans/VALIDATION_PLAN.md). The software output is experimental and
must first be evaluated on a stationary optical bench. It is not authorized for road
use or installation in the driver's primary field of view during vehicle operation.

## Software behavior

- Output is disabled by default.
- It can be enabled only when a secondary display is detected.
- White is treated as the stripped-TN-panel safe/transparent command.
- Valid in-bounds intersections produce feathered black spots.
- Lost eyes, lost lights, stale samples, Stop, and application shutdown clear spots.
- Exact right/bottom panel boundaries clamp to the last valid zero-based pixel.

Confirm the actual panel's polarization and voltage behavior before assuming white is
physically transparent. If the panel behaves oppositely, do not use this output until
the safe-state design is corrected and retested.

## Electrical and optical safety

- Use an isolated, current-limited bench supply and the correct controller board.
- Do not expose bare high-voltage backlight circuitry.
- Remove the backlight only with the panel powered off and discharged.
- Protect fragile panel conductors and sharp glass edges.
- Use an eye-safe diffused test lamp; never stare into a high-power beam.
- Provide a hardware method to remove power or force the transparent state.

## Phase A: panel characterization

Measure at the centre and at least four corners:

1. white-state visible transmission;
2. black-state transmission/attenuation;
3. contrast versus horizontal and vertical viewing angle;
4. polarization orientation and sensitivity;
5. grayscale response;
6. rise and fall time using a photodiode/oscilloscope or high-speed camera;
7. ghosting and image retention after repeated spots;
8. surface temperature during a one-hour worst-case pattern;
9. fail-state appearance after HDMI loss, controller reset, and power loss.

Record ambient illumination, lamp spectrum/intensity, sensor, distance, angle, panel
model, controller, refresh rate, and uncertainty.

## Phase B: pixel-to-physical mapping

1. Measure active LCD width/height, excluding bezel and inactive margins.
2. Display single-pixel/crosshair targets at centre, corners, and a minimum 5x5 grid.
3. Measure each target in the windshield coordinate frame.
4. Fit the LCD-to-windshield mapping without using validation points.
5. Validate on a separate interleaved grid.
6. Report mean, RMSE, p95, maximum error, distortion, and repeatability.
7. Repeat after panel/controller remounting.

Do not assume that nominal screen resolution maps uniformly to the full transparent
area. Record scaling, overscan, rotation, mirroring, and operating-system DPI settings.

## Phase C: blocker spot size

Choose radius from a declared error budget, not visual preference. Include:

- eye-position uncertainty projected to the panel;
- light-position/range uncertainty;
- camera-to-windshield and LCD-mapping error;
- motion during p95 end-to-end latency;
- pupil diameter and binocular separation;
- optical bloom/diffraction and panel viewing angle;
- a justified safety margin.

Test several radii and feather widths. Measure light attenuation at the pupil target
and loss of useful scene area. Record the smallest radius satisfying the attenuation
requirement across the full declared region.

## Phase D: dynamic and binocular validation

Use Stage 5 physical eye/light targets and Stage 6 timing instrumentation:

1. validate centre, edge, and corner intersections;
2. validate separate left/right-eye spots with head roll;
3. validate multiple simultaneous light sources;
4. move eye and lamp targets at declared maximum speeds;
5. measure overshoot, lag, flicker, spot dropout, and reacquisition;
6. inject every Stage 6 failure and measure time to all-white safe output.

## Acceptance record

Declare before final testing:

- minimum white-state transmission;
- minimum black-state attenuation;
- maximum pixel-to-physical RMSE and maximum error;
- maximum rise/fall time;
- maximum safe-state transition time;
- allowed temperature rise;
- maximum obscured field area;
- required binocular/multi-light coverage rate.

## Exit evidence

- panel/controller identification and electrical setup;
- raw optical measurements and uncertainty;
- pixel-grid fit and held-out validation results;
- blocker-radius derivation;
- dynamic, binocular, multi-light, and fail-safe videos/logs;
- documented safe-state behavior for signal and power failure.

Stage 7 remains incomplete until the physical panel meets every predeclared optical,
alignment, timing, thermal, and fail-safe limit.
