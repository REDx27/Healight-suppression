# Environmental and Vehicle-Like Validation Protocol

This is Stage 8 of the
[`Validation Plan`](../plans/VALIDATION_PLAN.md). Begin only after Stages 1–7 have passed
their applicable gates. The prototype must not be tested on public roads or presented
as an automotive safety device.

## Mandatory safety gates

Before any vehicle-like motion test, require documented approval that:

- the rig is stationary or on a controlled bench/closed course;
- a qualified supervisor and test operator are assigned;
- the driver does not depend on the prototype for visibility or safety;
- an independent operator can immediately remove LCD power/output;
- the panel defaults to its verified transparent state;
- all mounts have secondary retention;
- electrical, optical, thermal, and mechanical hazards are reviewed;
- emergency stop, abort criteria, exclusion zone, and communications are defined;
- applicable institutional, ethics, insurance, and local requirements are satisfied.

Failure of any gate prohibits the motion trial. Public-road testing is outside this
protocol.

## Freeze the tested configuration

Record software commit, executable hash, operating system, computer, camera devices,
firmware/drivers, lenses, resolutions, focus, exposure, mounts, intrinsic/extrinsic
profiles, LCD/controller, panel mapping, power supply, and acceptance limits.

Any change creates a new configuration ID and requires impact-based regression.

## Core metrics for every condition

- eye and light detection availability;
- false-positive and missed-detection rate;
- mean/RMSE/p95/maximum coordinate error;
- mean/RMSE/p95/maximum physical intersection error;
- stationary jitter and calibration drift;
- capture-to-geometry and external photon-to-display latency;
- maximum dropout and reacquisition time;
- stale-sample/fail-safe response time;
- video/telemetry drops;
- CPU, memory, GPU (if used), disk throughput, and temperatures;
- LCD transmission, attenuation, response, and panel temperature.

Use at least three independently reset repeats per condition. Randomize condition order
where practical and retain every failed run.

## Phase A: illumination and optical environment

Test on a stationary optical bench:

| Factor | Minimum levels |
|---|---|
| Ambient illumination | dark, dim road-like, indoor nominal, overcast daylight, bright daylight |
| Direction | front, rear/backlight, left side, right side, overhead |
| Light source | diffused test lamp, motorcycle-like single, car-like pair, multiple independent lights |
| Modulation | steady, 50/60 Hz exposure interaction, representative LED PWM/flicker |
| Background | dark, textured, windows, reflective signs, chrome/gloss, streetlight-like clutter |
| Driver | no glasses, clear glasses, sunglasses only if tracking is claimed, varied seating positions |

Measure exposure state, saturation/bloom, centroid stability, apparent diameter, false
selection, range error, and recovery after occlusion.

## Phase B: weather-like optical effects

Use controlled optical simulators without exposing unprotected electronics or people:

- clean/dry reference;
- water droplets/film on a sacrificial transparent sheet;
- controlled spray/fog chamber or optical fog medium;
- dust/dirty-sheet simulation;
- internal/external reflection layers;
- changing glare and scattered-light intensity.

Do not spray the camera, computer, stripped LCD, or energized controller unless the
hardware is specifically rated and the test plan has electrical approval.

## Phase C: temperature and endurance

Use declared equipment ratings and a monitored chamber or enclosure:

1. cold operating point;
2. ambient reference;
3. hot operating point;
4. thermal transitions and stabilization;
5. one-hour worst-case LCD pattern;
6. two-hour full-system run;
7. eight-hour endurance run after shorter stages pass.

Log component temperatures and stop before any rating, adhesive, battery, or glass
limit is approached. Recheck calibration and pixel mapping after thermal cycling.

## Phase D: vibration and mount stability

Begin with a non-operating inspection and low-level sweep. Progress only if mounts,
cables, and panel remain secure:

- idle-like low-frequency vibration;
- smooth-road-like broadband vibration;
- rough-road/pothole-like controlled pulses within fixture ratings;
- axis-by-axis X/Y/Z excitation;
- combined camera and panel mount excitation.

Measure image blur, tracking dropout, timestamp skew, physical intersection error,
mount displacement, connector faults, and post-test calibration drift. Use secondary
retention and an exclusion zone around glass/panel components.

## Phase E: stationary vehicle-like rig

Install the complete system in a stationary mock cabin or parked test vehicle in a
controlled private area. Keep the vehicle immobilized. Test seating adjustments,
head movement, realistic camera angles, windshield reflections, dashboard lighting,
multiple lamps, occlusions, and electrical transients from accessory power.

Validate all Stage 6 failure injections again in this configuration.

## Phase F: closed-course motion (conditional)

Only after all earlier phases pass and formal approval is recorded:

- use a closed, controlled course at progressively increased but bounded speeds;
- retain an unobstructed independent field of view;
- use a safety driver who does not interact with the software;
- have a separate test operator and immediate hardware disable;
- begin with no active blocker, then static patterns, then controlled tracking;
- abort on any unexpected opacity, stale spot, camera/mount movement, UI failure,
  thermal alarm, distraction, or loss of communications.

No public traffic, uninvolved road users, pedestrians, or dependency on the system is
permitted.

## Combined worst-case matrix

After one-factor testing, select justified combined cases rather than claiming full
factorial coverage. Include at least:

- bright backlight + glasses + lateral head pose;
- dark environment + multiple LED sources + reflections;
- hot stabilized system + maximum recording load;
- vibration + moving eye/light targets;
- partial occlusion + source crossing + exposure transition;
- worst measured latency + maximum declared target speed.

Document why each combination represents a boundary and which combinations remain
untested.

## Acceptance and reporting

Predeclare limits for every core metric and condition family. Report results by
configuration ID and condition, with uncertainty, repeat count, failures, exclusions,
and raw evidence links. A global pass is prohibited if any safety-critical condition
is missing, unmeasured, or outside its limit.

## Exit evidence

- signed hazard review and approvals;
- frozen configuration manifest;
- complete condition matrix and predeclared limits;
- synchronized raw CSV/video and setup/environment records;
- statistical summaries and uncertainty;
- before/after calibration and mount measurements;
- endurance resource/temperature logs;
- documented failures, corrective actions, and residual limitations.

Stage 8 is complete only when evidence supports every declared operating boundary.
It does not by itself certify the prototype for automotive use.
