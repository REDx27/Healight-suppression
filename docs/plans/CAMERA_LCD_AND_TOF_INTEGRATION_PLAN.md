# Installed Camera-to-LCD and Driver ToF Integration Plan

**Created:** 2026-11-24<br>
**Status:** Host calibration/live-integration software implemented; controller firmware
and physical validation outstanding (2026-11-24)
**Source reviewed:** `e1bd51d`, GlareTracker v1.3.0 plus prototype-display integration<br>
**Hardware:** two road webcams, one driver webcam, purchased GY-VL53L0X sensor,
and the existing secondary LCD monitor<br>
**Purpose:** implementation sequence for the next development phase, with separate
software and physical acceptance gates.

## 1. Outcome in plain language

### Implementation update - 2026-11-24

The source now contains mode-aware calibration buttons, independent driver camera/ToF
dialogs/skips, measured off-panel pose fitting, physical LCD mark fitting, saved profile
bindings, native driver geometry, rectification-aware installed road reconstruction,
host bridge-v1 serial parsing, limited-region ToF fusion, and timed output expiry.
182 automated tests pass; 44 were added for this integration. Dialog layouts were
inspected offscreen. See the [operator guide](../guides/DRIVER_AND_INSTALLED_RIG_CALIBRATION_GUIDE.md)
and [bridge contract](../reference/TOF_BRIDGE_PROTOCOL.md).

Not completed: MCU firmware/wiring, real sensor connection, hardware timestamp
validation, full pose/face-target association, physical end-to-end calibration,
optical attenuation and recorded accuracy/latency evidence. The sensor has no controller
connected. Existing code-guide PDFs describe the earlier source. The remaining sections
retain the staged plan and intended physical acceptance targets; they do not claim every
planned item is implemented or any physical gate has passed. No version/build bump.

The application must learn where each camera is relative to the LCD, including its
small mounting angles. It must then express the detected lights and both eyes in
the same physical coordinate system before calculating intersections.

The ToF sensor will add a measured face-distance reference to the driver webcam.
The webcam still finds the two irises and supplies drowsiness landmarks. ToF does
not locate the eyes, and its face-surface reading is not automatically eye depth.

The intended processing is:

```text
Road LEFT + RIGHT pixels
  -> calibrated stereo reconstruction in a named camera frame
  -> installed road-camera-to-LCD transform
  -> light positions in LCD centimetres

Driver iris pixels + calibrated camera + valid distance source
  -> two eye estimates in the driver-camera frame
  -> installed driver-camera-to-LCD transform
  -> eye positions in LCD centimetres

Eye positions + light positions
  -> existing ray/plane intersection
  -> LCD pixel mapping and blocker output
```

This work integrates coordinates and driver ranging. Manufacturing the transparent
panel, redesigning light detection, and adding prediction are separate tasks.

## 2. What exists and what must change

| Area | Current implementation | Planned integration |
|---|---|---|
| Lens/stereo calibration | Guided road LEFT/RIGHT/stereo workflow and NPZ profiles | Reuse; add genuine driver-camera checkerboard intrinsics |
| Installed poses | `extrinsics.py` has rigid transforms, solvePnP, identity checks and JSON profiles | Add measured jig sessions, appropriate off-panel validation and live profile application |
| Extrinsic CLI | Accepts XYZ fit targets, but validates by intersecting rays with `Y = 0` | Preserve that legacy path; add a distinct general-3D jig validation path |
| Road coordinates | Rectified disparity plus assumed half-baseline/height placement | Reconstruct camera-frame XYZ, account for rectification, apply measured installed pose exactly once |
| Driver coordinates | Mirrored image, manual/IPD depth, approximate panel placement | Native-image geometry, explicit distance-source result and measured installed pose |
| Centre calibration | Automatically subtracts an X/Z offset from live eye positions | Bypass in installed physical mode; retain as a clearly labelled demo function |
| ToF | No firmware, serial dependency or fusion in the application | Firmware bridge, timestamped USB transport, sensor calibration and validity-aware fusion |
| Freshness | Callback checks; missing timing can pass; no independent silence watchdog | Typed observations, strict physical-output readiness and periodic expiry checks |
| Evidence | CSV/video recorder and offline analysis tools | Record profile IDs, raw/fused distance, time pairing and rejection reasons |

The previously recorded 138 passing tests are the baseline, not new verification of
these proposed features. The existing PDF code guides describe the pre-integration
source and will need updating after implementation.

## 3. Design decisions

### One physical reference frame

Keep the existing LCD convention: origin at the bottom-centre of the active pixel
area; X sideways, Y toward the road, Z upward; LCD plane `Y = 0`. The driver has
negative Y and the road has positive Y. Distances inside the application are cm.
Firmware transmits mm, converted once at the Python boundary.

Use raw OpenCV camera coordinates for reconstruction and pose profiles. Do not
pre-apply panel height, half-baseline shifts or manual sign swaps before the installed
transform. Every observation carries its frame name and profile generation.

OpenCV's pose and rectification conventions determine the conversion order. For the
road path, triangulate rectified correspondences using P1/P2, divide homogeneous
coordinates, then undo R1 to recover raw LEFT-camera XYZ before applying its installed
pose. Alternatively reconstructed coordinates must carry an explicitly equivalent
rectified-frame transform; mixing the frames is forbidden. See the
[OpenCV calibration reference](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html).

### Preview mirroring is separate from geometry

Calibrate and measure in the native, unmirrored image coordinates. Mirror only the
driver preview. If MediaPipe processing remains mirrored for compatibility, map all
relevant landmarks back to native pixels before unprojection and head-pose fitting;
converting only the irises would leave head pose inconsistent. Preserve anatomical
eye identity and test it explicitly. Crop, rotation, mirroring and resolution belong
to the profile compatibility contract.

### Installed mode and demonstration mode are explicit

Installed mode accepts only compatible, passing profiles and valid observations.
It does not automatically recenter eyes, substitute an assumed road distance or
silently replace failed ToF with IPD. Demo/manual modes remain available with their
existing purpose and clear labels. Manual coordinates entered for a measured bench
test must already be in the LCD frame.

IPD-only driver tracking can be evaluated separately. Its use for physical output
requires its own held-out validation, rather than inheriting the ToF profile's pass.
Explicit display test patterns remain available independently of tracking readiness.

### Hardware and transport assumptions

Use the purchased VL53L0X module over I2C and a USB serial bridge to the laptop.
The reference firmware target is an ESP32 development board with a USB connection;
an already-owned Arduino Nano/Uno can be used if its firmware build, memory use and
range-quality reporting pass the same contract. Confirm the actual board before
writing its pin map; this plan does not require a purchase. ATtiny85/Pro Mini size
optimization is deferred until the USB prototype works.

Use a driver exposing measurement status, not just a number. The starting candidate
is Adafruit's ST-API-based VL53L0X library, pinned to a tested release at implementation.
Do not treat the example's single out-of-range check as the complete validity policy.
Pololu's small library is an alternative, but its documented reduced error checking
must be addressed before enabling physical output. References:
[Adafruit example](https://github.com/adafruit/Adafruit_VL53L0X/blob/master/examples/vl53l0x/vl53l0x.ino),
[Pololu library](https://github.com/pololu/vl53l0x-arduino),
[ESP32 USB serial](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/establish-serial-connection.html),
[classic Nano](https://docs.arduino.cc/hardware/nano/).

## 4. Workstream A: installed camera-to-LCD calibration

### A1. Prepare the rig and calibration prerequisites

1. Fix the LCD and all cameras rigidly. Road cameras face the road; driver camera
   faces the driver. They remain in those directions during installed calibration.
2. Record the active pixel edges, origin, camera/mount IDs, approximate optical-centre
   positions, baseline and selected panel profile. Recheck the recorded P203
   dimensions, 44.28 x 24.91 cm, on the final rig.
3. Verify road intrinsic/stereo profiles at the actual runtime resolution and focus.
   Add driver intrinsic calibration using a rigid flat checkerboard and the existing
   single-camera calibration backend. The one-point IPD focal estimate is not a
   substitute for lens calibration.
4. Record the filter installation state. Calibrate without dark filters initially,
   then verify geometry in the final optical assembly. A failed post-filter check
   requires a suitable recalibration/verification procedure, not assumed equivalence.

No existing road calibration is discarded merely because installed-pose support is
added. Keep it if its device/order/settings checks and physical verification pass.

### A2. Add a measured checkerboard-jig workflow

For lens calibration the board moves freely. For installed calibration, every board
pose must be independently known relative to the LCD.

Use a flat board on a measured rail/stand with repeatable positions. Begin with
parallel board placements at known X/Y/Z offsets to avoid measuring arbitrary angles
by hand. Place it on the road side for road cameras and driver side for the driver
camera, facing the relevant camera. Support measured tilted placements when needed;
their full orientation must be recorded.

The new session format records:

- rig/panel identity, dimensions, mount revision and measurement uncertainty;
- ordered camera identities, native image geometry and intrinsic fingerprints;
- checkerboard rows/columns, measured square size and corner origin/directions;
- a board-to-LCD rigid pose for each placement, producing known LCD XYZ for each corner;
- unscaled raw frames, timestamp, detected corners and capture settings;
- fit or held-out status assigned by complete board placement before fitting;
- acceptance limits declared before validation.

Give the board a visible orientation mark. A symmetric checkerboard can reverse its
corner ordering; the workflow must confirm corner origin/directions rather than
silently fitting the wrong correspondence.

Initial capture proposal: at least six fit placements spanning image area and at
least three depth planes; at least three separate held-out placements. This is a
collection minimum, not a quality guarantee. Corners from one placement must not be
split across fit and validation. Repeat the full physical session three times.

### A3. Fit and validate without projecting unseen targets onto the LCD

Reuse solvePnP and the rigid-transform helpers. Fit the driver camera and raw road
LEFT camera to the LCD frame. Derive road RIGHT's active pose from the LEFT pose and
the saved stereo relationship; an independently fitted RIGHT pose can cross-check
that relationship rather than establish a conflicting second stereo anchor.

Validation is separated by what is observable:

- **Single-camera pose:** held-out reprojection error, positive target depth,
  independently measured camera-position plausibility and point-to-ray residual in
  cm for the known off-panel targets. A point-to-ray residual measures transverse
  agreement; it does not independently establish range accuracy.
- **Stereo:** reconstruct held-out board corners/targets and compare full XYZ in
  the LCD frame with independent measurements, including depth error.
- **Driver:** compare reconstructed eye targets at known depths with measured XYZ.
  A 2D landmark alone cannot supply independent 3D validation.
- **Final intersections:** compare eye/light crossings with independent physical
  panel marks after both coordinate paths pass.

Keep the existing `Y = 0` CLI mode for cameras that can see that plane. Do not apply
its forward ray-plane validator to the final outward-facing installation. All fit
attempts retain reports; only passing candidates become activatable profiles. A
failed attempt must not overwrite the last passing profile or imply it is current
after a mount change.

### A4. Profile and live-pipeline integration

Add a versioned rig manifest referencing driver intrinsics, road stereo, installed
poses and later ToF profiles. Include panel origin/axes, native image convention,
filter state, mount revision, validation status/limits and evidence/report paths.
Do not relabel existing v1 files as fully validated new-format profiles.

Device matching must address cheap identical webcams: index and friendly name alone
cannot distinguish them. Prefer a persistent OS device path/serial when available;
otherwise require explicit LEFT/RIGHT/driver confirmation with a preview or lens-cover
check before arming output after discovery changes. Do not silently trust reordered
USB indices. Mechanical movement still requires operator invalidation; software
cannot detect every mount movement from metadata.

The live road path will:

1. retain candidate detection and one-to-one matching;
2. reconstruct matched points with calibration P1/P2;
3. reject invalid homogeneous coordinates, behind-camera points and excess residuals;
4. undo rectification, apply the measured LEFT-to-LCD pose once;
5. publish LCD-frame candidates to temporal tracking, retaining source timestamps.

The live driver path will:

1. obtain two iris pixels in the native image convention;
2. select an explicit valid depth result: IPD comparison first, ToF after Workstream B;
3. undistort and unproject into the raw driver-camera frame;
4. apply the installed driver-camera-to-LCD pose once;
5. publish both eyes without the automatic centre offset.

Reset temporal tracks, depth filters, cached eyes and blocker output on profile,
camera-role or coordinate-frame changes. Never blend positions from different
profile generations. Keep existing geometric intersection and LCD mapping functions.

## 5. Workstream B: ToF acquisition and driver-eye fusion

### B1. Firmware and wire protocol

The microcontroller reads the sensor and reports observations. All eye estimation,
fusion and intersection calculation stay in Python.

Proposed protocol v1: newline-delimited JSON at 115200 baud, bounded to 512 bytes per
line. Start with 20 measurements/second and a recorded measurement budget near
33 ms; actual rate/budget must be supported by the selected library and measured.
ST documents timing/ambient/target-dependent performance in its
[datasheet](https://www.st.com/resource/datasheet/vl53l0x.pdf) and
[API manual](https://www.st.com/resource/en/user_manual/dm00279088-world-smallest-timeofflight-ranging-and-gesture-detection-sensor-application-programming-interface-stmicroelectronics.pdf).

The protocol contains three message types:

| Message | Required information |
|---|---|
| HELLO | Protocol/firmware/library version, configured device ID, sensor model, session token echoed from the host, measurement budget and capabilities |
| RANGE | Session token, sequence number, measurement start/end MCU uptime, raw mm or null, normalized validity, original sensor status, timeout flag and available signal/ambient quality fields |
| SYNC reply | Host request ID plus MCU receive/send uptimes for bounding clock offset and serial delay |

Define each status translation against the chosen library/API and unit-test it.
Timeout, I2C error, weak/invalid return and out-of-range are distinct from valid.
Never invent quality values or assume a missing quality field means success.
Advertise unsupported fields in HELLO. Physical mode requires a supported minimum
status/timeout contract; extra quality fields are retained when available.

A host-generated session token is renewed on each connect/reset, so a low-cost board
does not need an assumed hardware serial number or a reliable random boot ID.
Configured module/mount identity is still checked. Firmware bounds I2C waits and sends
invalid status on sensor failure; serial output is kept separate from debug text.

### B2. Python serial service

Add `pyserial` at implementation and include it in packaging checks. A dedicated
worker owns the serial connection, parser and reconnect state. The GUI and camera
threads never block on serial reads.

The service will:

- list ports; let the operator select the device; accept only a matching HELLO;
- use finite read timeouts and bounded buffers; reject malformed, oversize,
  duplicate, out-of-order and incompatible packets;
- convert mm to cm once and publish immutable samples with host receive time;
- map MCU uptime into host monotonic time using repeated request/reply exchanges,
  recording uncertainty and rejecting ambiguous clock mappings;
- distinguish counter rollover from reboot, flush old samples on either reset or
  reconnect, and never mark backlog as fresh merely because it just arrived;
- retry a confirmed device with bounded backoff; require several fresh valid samples
  before returning to Ready; release the port on Stop/shutdown.

Start/Standby/Stop behaviour: Run and Standby can keep the configured sensor active
when a driver-camera/ToF mode needs it; only Run calculates live blockers. Stop closes
the serial port. Manual-driver mode does not require a ToF connection. Opening some
USB boards resets them; handshake state must handle that normally.

### B3. Calibrate sensor geometry and face-to-eye offset

Mount the sensor rigidly near the driver camera and aim at the forehead/upper face.
Record the sensor origin/direction relative to the raw camera frame and its physical
mount. Use independently measured targets at several seating depths to estimate
range bias, repeatability and the conversion into camera-axis depth.

VL53L0X is a single-zone device: ST's performance conditions use a 25-degree FoV.
It cannot identify which facial point or background surface supplied the return.
At 50 cm, a simple 25-degree cone spans about 22 cm; this is an illustrative geometry
calculation, not a guaranteed sensing footprint. The practical consequence is that
head position and background interference must be tested, not hidden by smoothing.
[Sensor reference](https://www.st.com/resource/datasheet/vl53l0x.pdf).

Use two separate calibration records:

1. **Sensor/mount record:** range bias, usable interval, sensor-to-camera translation
   and direction, quality limits, timing settings and held-out target evidence.
2. **Driver/session record:** measured correction between the ranged facial surface
   and the eye plane, participant/reference ID, and validated head-position/pose limits.

Initial fusion is deliberately limited to a near-frontal, centred head inside the
measured valid region. A simple surface-to-eye correction is accepted only in that
region. Leaving it invalidates the ToF eye estimate. General head-turn compensation
requires a validated facial model and per-eye depths; it is not obtained from a
constant offset or one scalar range reading.

For that restricted first model, define the calculation explicitly:

```text
corrected_range_cm = raw_range_cm + calibrated_sensor_bias_cm
surface_point_camera = sensor_origin_camera + corrected_range_cm * sensor_axis_camera
eye_depth_camera = surface_point_camera.Z + calibrated_surface_to_eye_Z_offset_cm
eye_point_camera = eye_depth_camera * (undistorted_x, undistorted_y, 1)
eye_point_LCD = installed_driver_transform(eye_point_camera)
```

The surface point is a calibrated central-axis approximation to a single-zone return,
not a point identified by the sensor. Its validity must be measured. Begin the test
matrix around 40-90 cm and yaw/pitch within +/-10 degrees, with a measured central
head region; these are proposed trial bounds, not accepted operating limits. Record
and narrow them if the actual device/face/background cannot satisfy the error target.

Calibrate sensor offset on rigid targets, then evaluate facial-surface behaviour with
real participants. Keep independent fit and validation distances and report them
separately. Moving/refitting the sensor or adding a cover invalidates its profile.

### B4. Pair, validate and reconstruct the two eyes

For each camera observation:

1. Select the nearest eligible ToF sample in the small timestamped history; never
   wait indefinitely for it. A short bounded delay is allowed only within the pairing
   budget and is included in latency measurements.
2. Require compatible profiles, two usable iris observations, valid sensor status,
   acceptable age/skew/clock uncertainty, and head position inside the validated region.
3. Convert the calibrated face range to camera-axis eye depth using the sensor and
   driver/session records. Do not substitute radial range directly for optical Z.
4. Reconstruct both camera-frame eye positions, then apply the installed pose.
   The first version uses a common eye-depth approximation only within its validated
   frontal-pose range; it does not claim arbitrary yaw accuracy.
5. Record raw range, corrected eye depth, IPD comparison, chosen source and validity.

Do not average IPD and ToF arbitrarily. Initially ToF is the explicit selected source;
IPD is recorded for comparison and disagreement detection. A large disagreement
invalidates the result until explained by calibration/pose rather than automatically
choosing the smoother value. If a validated depth filter is added, bound its lag and
expire it using the last actual valid measurement time.

If the eyes disappear, ToF alone cannot keep a blocker active. If ToF fails in ToF
mode, output clears rather than silently switching source. Drowsiness remains a
separate camera-landmark feature and can continue when range is unavailable.

## 6. Shared observation, readiness and timing rules

Introduce small immutable observation records for eyes, road sources and range.
Include frame/sample ID, source/session identity, measurement time interval,
clock uncertainty, profile generation, frame name, validity/reason and payload.
The new installed path consumes one typed signal per observation; legacy scalar
signals, if retained for demo adapters, must not trigger duplicate calculations.

Keep raw eye pixels available to a pure driver-depth estimator. The serial service
provides a thread-safe snapshot/history, not widget access from the camera worker.
Tie each timing record to its observation instead of a separate 'latest timing'
dictionary. Road LEFT/RIGHT host capture skew must also be recorded and checked;
these USB webcams are not hardware synchronized.

Provisional development defaults below are targets to test, not achieved results or
approved thesis limits. Freeze actual configuration/limits before held-out collection.

| Setting | Initial proposal | Reason/check |
|---|---|---|
| ToF sampling | 20 Hz | Measure achieved rate and return validity |
| Maximum ToF age | 100 ms | Prevent old range being reused |
| Eye/ToF effective-time difference | 50 ms, including uncertainty | Reject mismatched observations; tighten if motion error requires it |
| Clock-mapping uncertainty | At most 20 ms | Otherwise range is not eligible for physical fusion |
| Camera sample age | At most existing 250 ms ceiling | Measure and reduce for final motion/error budget |
| Road LEFT/RIGHT skew | Initial ceiling 50 ms | Static prototype only; moving-light validation may require a smaller limit |
| Expiry watchdog | Every 25 ms while Run | Detect silent camera/serial stalls without waiting for a new callback |
| Clearing target | Within 200 ms of last valid required input on an otherwise responsive app | Stale state clears; record measured maximum and scheduling jitter |
| Recovery | Three consecutive valid, compatible, paired observations | Avoid rearming on one isolated return |

The 200 ms physical-output freshness target takes precedence over a looser incoming
camera limit. Record latest raw-valid source times; do not refresh them with a held
track, filter prediction or repeated receipt. Once input validity expires, clear LCD
spots and related intersections. A valid next callback must not briefly rearm output
using the other source's expired cached data.

One readiness calculation covers every route into physical tracking output:

```text
Run + output armed + valid display/panel mapping
+ compatible required camera/rig/depth profiles
+ fresh required eyes/range/lights with acceptable cross-stream skew
+ matching observation/profile generation
= live tracking may update physical spots
```

Validate driver-versus-road observation skew too, not just eye-versus-ToF skew. Begin
with the same 50 ms proposal and record the true measurement intervals. Manual inputs
are explicit constants in the LCD frame. Test patterns are an explicit separate
output state and must not be overwritten by incidental tracking callbacks.

Calibration, display/topology changes, camera reassignment, profile reload and reconnect
immediately clear dependent cached results. Software expiry does not establish
behaviour during a frozen operating system or power/controller failure.

## 7. Operator interface

Keep the existing six-context layout; add controls to the relevant context rather
than creating another long advanced-settings form.

| Location | Planned controls/feedback |
|---|---|
| Cameras | Installed Rig Calibration button; driver intrinsics; per-camera/profile state |
| Geometry | Rig/panel identity, measured origin/mount revision, passing installed profiles |
| Driver | Depth source: Manual / IPD comparison / ToF; serial port, Connect/Test, range/status/age, sensor and eye-offset calibration |
| Research | Raw versus corrected depth, selected source, profile hashes, rejection counts and recorded session path |
| Header/telemetry | Ready, Needs Calibration, Connecting, Invalid Range or Stale Input, with the blocking reason |

Guided installed-calibration sequence: check identities/settings -> explain the two
sides of the rig -> enter/confirm jig measurements -> capture fit placements ->
capture separate validation placements -> fit -> show metrics/pass/fail -> explicit
Save and Activate. Capture/solve work runs off the GUI thread. Close/cancel releases
camera ownership and restores the previous session with physical output still gated.

Provide progress, actionable rejection reasons and an explicit successful-save alert.
Skip permits previews/demo use; it does not mark calibration complete. ToF calibration
similarly shows raw mm/cm, corrected eye depth, quality and held-out error before save.

## 8. Files and responsibilities

Names for new files below are proposed; avoid duplicate geometry or a second tracking
engine during implementation.

| File/area | Planned responsibility |
|---|---|
| `glare_tracker/extrinsics.py` | Reuse transforms; add jig-coordinate/validation and versioned profile support |
| `scripts/calibrate_extrinsics.py` | Explicit legacy-plane versus measured-3D input/report modes |
| `glare_tracker/calibration.py` | Genuine driver lens calibration and profile identity support |
| New `glare_tracker/observations.py` | Immutable, timestamped and frame-labelled observation contracts |
| New `glare_tracker/tof.py` | Serial service, parsing, clock mapping and connection state |
| New `glare_tracker/driver_depth.py` | Pure calibration, validity, pairing and depth/eye reconstruction logic |
| `glare_tracker/camera.py` | Native iris/pose geometry and typed driver results |
| `glare_tracker/headlight_detector.py` | Proper stereo-camera reconstruction and installed transformation |
| `glare_tracker/tracking.py` | Consume LCD-frame points; bypass demo recentering; clear dependent caches |
| `glare_tracker/window.py` | Own service/dialog lifecycle, profile readiness and watchdog routing |
| `glare_tracker/widgets/controls.py` | Organized calibration/depth controls and concise status |
| New widgets under `glare_tracker/widgets/` | Installed-rig and ToF calibration dialogs, reusing existing capture workers |
| `glare_tracker/diagnostics.py` | Raw/fused depth, profile, skew and rejection evidence |
| New `firmware/vl53l0x_bridge/` | One tested board implementation, protocol documentation and library versions |
| `requirements.txt`, packaging and tests | Serial dependency, reproducible build and targeted regression coverage |

The existing `geometry.py` intersection formula, LCD renderer and drowsiness
algorithm are retained; extend their callers/contracts only where integration needs it.

## 9. Ordered implementation and completion gates

Each stage should be independently reviewable. Physical gates stay open until the
rig/evidence exist; synthetic tests do not complete them.

| Order | Work | Completion gate |
|---|---|---|
| 0 | Save baseline; define observations, units, frame conventions, limits and fixture data | Current demo/display behaviour is reproducible; known baseline issues are recorded |
| 1 | Extend extrinsic backend/CLI for measured off-panel jig data and profiles | Synthetic rotated/translated rig fits, split validation, invalid data and compatibility cases pass |
| 2 | Add driver intrinsics and installed-calibration UI | Full capture/fit/fail/save/cancel/reload workflow works without camera ownership conflicts |
| 3 | Integrate road pose first in Driver Position Fixed mode | Held-out road XYZ and physical crossings pass with measured manual eyes; no assumed mounting shifts remain in installed mode |
| 4 | Integrate driver pose with explicit IPD comparison depth; disable physical recentering | Known driver targets transform correctly; pose errors can be separated from depth errors |
| 5 | Build firmware + serial service; use replay fixtures before hardware | Protocol, invalid status, clock mapping, silence/reset/disconnect/reconnect tests pass; actual board streams raw evidence |
| 6 | Add ToF bias/mount/face-offset calibration and fusion | Held-out driver eye-depth/XYZ tests pass within a declared pose region; invalid source cannot leave live spots |
| 7 | Combine both installed pipelines and finish regression/bench validation | Multi-eye/multi-light physical mapping, timing, recovery, recording soak and packaged application checks pass |

Firmware/serial preparation can proceed before the final rig exists. Final installed
profiles and sensor offsets must be collected on that rig. Begin end-to-end tests
with measured artificial eye/light targets, then participants; avoid masking road
and driver errors by tuning both simultaneously.

## 10. Test plan and measurable evidence

### Software checks

- Pose recovery for translated/rotated road and driver cameras; transformation
  direction, frame-name/units checks and native/mirrored pixel handling.
- Non-identity R1 stereo reconstruction, asymmetric camera placement, negative
  depths, invalid disparities, camera-order swaps and profile-generation changes.
- Jig orientation/corner reversal, duplicate/degenerate targets, incorrect square
  scale, independent pose-level hold-outs, failed save and legacy profile handling.
- Driver installed mode cannot apply centre recentering or apply a transform twice.
- Serial chunking, partial lines, malformed/oversize packets, status codes, timeouts,
  sentinel values, MCU rollover/reboot, backlog, wrong device and clock uncertainty.
- Range-to-axis and face-to-eye conversion, missing eyes, head outside valid region,
  stale/out-of-order pairing, IPD disagreement and strictly labelled source changes.
- Fake-clock expiry and recovery tests, including completely silent workers and
  independent driver/range/road staleness. Exercise every path into LCD updates.
- Qt functional tests for wizard stages, cancel/close, save activation, camera release,
  port lifecycle, Run/Standby/Stop, explicit test patterns and existing drowsiness use.

Run focused tests while implementing each stage and the full existing suite at
integration milestones. Perform a packaged-launch smoke test once serial/profile
support is included. Do not rerun or report the old 138-test count as new evidence.

### Physical checks and draft targets

The numbers below are proposed starting goals, not observed capability. Record
justified acceptance limits in the relevant measurement protocols before held-out
trials. Preserve failed runs; report failures or restrict the operating region
instead of adjusting limits after seeing results.

| Measurement | Initial engineering goal | Evidence |
|---|---|---|
| Installed-pose fit | Reprojection RMSE <= 1 px | Raw frames, target poses and fit report |
| Single-camera held-out transverse agreement | p95 <= 1 cm; maximum <= 2 cm | Point-to-ray residual plus pose plausibility; explicitly not a depth claim |
| Corrected driver eye depth | RMSE <= 1 cm; p95 <= 2 cm | Independent eye-depth references, IPD/ToF A/B runs and dropout rate |
| Complete panel intersection | p95 <= 1 cm; maximum <= 2 cm | Independent physical panel marks for both eyes and multiple lights |
| Timing/expiry | Meet Section 6 limits | Capture/range intervals, pairing/skew, watchdog and visible-clear measurements |
| Endurance | Clean ten-minute three-camera + ToF recording | Decodable video, finalized logs, drop/error counts and verifier report |

Evaluate several measured driver distances, lateral/vertical head positions, yaw,
glasses, ordinary lighting and incoming LED/high-IR glare. Test a foreground hand
and a background surface to expose wrong-target ToF returns. Compare IPD-only and
ToF-based estimates at the same positions without using the validation samples to
fit either correction. Test road lights near 2-3 m at centre and common-FOV edges,
then moving cases only after stationary geometry passes.

Record mean/bias, RMSE, p95, maximum, jitter, valid-reading rate and dropout duration;
report unsupported poses/lighting. If ToF fails the required accuracy or availability,
keep it disabled for physical tracking and retain the measured result as research
evidence. A better sensor or driver stereo would then be a separate decision.

## 11. Research records and handoff

Save each run's rig manifest, calibration/profile hashes, board measurements and
uncertainty, camera/firmware/library versions, source commit, raw data and reports.
Extend diagnostics with raw/corrected range, source, status, sample IDs/times, skew,
clock uncertainty, depth rejection and clearing/recovery events. Version log-schema
changes and adapt existing offline tools without silently breaking old recordings.

Update the thesis/design reference and technical brief after each implemented or
physically verified milestone, clearly separating those two states. Refresh code
guide PDFs after source changes. No version bump, implementation claim or new
physical-test pass is created by writing this plan.

Related records:

- [Ordered validation plan](VALIDATION_PLAN.md)
- [Camera-to-windshield protocol](../protocols/CAMERA_TO_WINDSHIELD_CALIBRATION_PROTOCOL.md)
- [Ground-truth measurement protocol](../protocols/GROUND_TRUTH_MEASUREMENT_PROTOCOL.md)
- [Physical intersection protocol](../protocols/PHYSICAL_INTERSECTION_TEST_PROTOCOL.md)
- [Latency and recovery protocol](../protocols/LATENCY_AND_RECOVERY_TEST_PROTOCOL.md)
- [Meeting technical brief](../reference/PROGRESS_MEETING_TECHNICAL_BRIEF.md)
- [Thesis and design reference](../reference/THESIS_AND_DESIGN_REFERENCE.md)
