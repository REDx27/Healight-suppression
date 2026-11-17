# Physical LCD Validation Protocol

This is Stage 7 of the
[`Validation Plan`](../plans/VALIDATION_PLAN.md). The software output is experimental and
must first be evaluated on a stationary optical bench. It is not authorized for road
use or installation in the driver's primary field of view during vehicle operation.

## Software behavior

- Output is armed by default but opens only in **Run** when a selected non-primary
  display is detected. It never intentionally targets the operator's primary screen.
- **Standby**, **Stop**, display removal, and application shutdown clear the spots,
  hide the output window, and release the display desktop.
- White is the initial maximum-transmission hypothesis; black inverse mode is provided
  to determine the actual panel polarity before selecting the physical safe state.
- Under white-clear mode, valid in-bounds intersections produce feathered black spots;
  inverted mode reverses the colours for bench testing.
- Safe Fill, Center Spot, and Corners + Center patterns are available for alignment.
- Lost eyes, lost lights, rough/uncalibrated sources, stale samples, invalid geometry,
  Standby, Stop, and application shutdown clear physical spot authority.
- Exact right/bottom panel boundaries clamp to the last valid zero-based pixel.
- The built-in HP ProDisplay P203 profile records a 44.28 x 24.91 cm active image
  area. The connected controller was observed at 1600 x 900; verify both dimensions
  against the disassembled final panel before accepting the mapping.

Confirm the actual panel's polarization, retained optical layers, and voltage behaviour
before assuming white is physically transparent. If black transmits more light, select
the inverse mode and repeat every clearing/failure test. The safe state is defined by
measured maximum transmission, not by the software colour name.

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
Begin with the built-in Center Spot and Corners + Center patterns to detect rotation,
mirroring, clipping, and wrong-screen routing; then use the denser measurement grid for
the actual fit.

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
6. inject every Stage 6 failure and measure time to the physically verified maximum-
   transmission safe output.

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
