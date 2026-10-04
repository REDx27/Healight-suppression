# Temporary UI and Camera-Mode Implementation Checklist

> Created: 2026-10-02  
> Purpose: keep the UI/camera redesign ordered, testable, and resumable.  
> Rule: mark an item complete only after its acceptance checks pass.

## Agreed operating model

### Session states

| State | Cameras | Coordinate calculations | Intended use |
|---|---|---|---|
| **Run** | Required cameras active | Active in real time | Execute the selected operating mode |
| **Standby** | Required camera previews active | Paused/frozen | Position cameras, driver, and test lamp safely |
| **Stop** | All cameras released | Stopped and cleared | End the session or change hardware |

### Operating modes

| Mode | Driver position source | Headlight position source |
|---|---|---|
| **Fully Auto** | Driver camera | Road camera(s) |
| **Fully Manual** | Manual X/Y/Z | Manual X/Y/Z |
| **Driver Position Fixed** | Manual X/Y/Z | Road camera(s) |
| **Headlight Position Fixed** | Driver camera | Manual X/Y/Z |

“Fixed” means that the position is supplied manually and remains constant until the
operator changes it. Camera selection and calibration controls must only be enabled
when the selected mode uses that camera.

## Implementation checklist

- [x] **T01 — Add explicit Run / Standby / Stop session control**
  - Run starts the cameras required by the selected mode and accepts tracking results.
  - Standby keeps the required previews live but does not update ray/intersection data.
  - Stop releases every camera, stops movement simulation, and clears live tracking.

- [x] **T02 — Add the four operating modes**
  - Fully Auto, Fully Manual, Driver Position Fixed, Headlight Position Fixed.
  - Replace the confusing independent Manual/Auto light switch with one mode selector.
  - Show a short plain-language description of the active sources.

- [x] **T03 — Lock irrelevant configuration controls by mode**
  - Fully Auto: lock manual driver and light coordinates.
  - Fully Manual: unlock both manual coordinate groups; lock camera calibration controls.
  - Driver Position Fixed: unlock driver coordinates; enable only road-camera setup.
  - Headlight Position Fixed: enable only driver-camera setup; unlock light coordinates.

- [x] **T04 — Make single/stereo road setup contextual**
  - Show road-camera setup only in modes that track the headlight.
  - Show the single-camera calibration action only for Single Camera.
  - Show the second road-camera selector only for Stereo Cameras.
  - Display an explicit warning that single-camera distance is estimated/assumed.

- [x] **T05 — Display separate stereo road-camera previews**
  - Single mode shows one road preview.
  - Stereo mode shows primary and secondary road previews as separate cards.
  - Manual headlight modes hide road preview cards that are not in use.

- [x] **T06 — Rebuild the main workspace layout**
  - Keep the windshield preview aligned at the upper-left of the 3D space.
  - Place telemetry/coordinates at the upper-right of the 3D space.
  - Give telemetry a slightly transparent compact background.
  - Move camera feeds to a bottom strip, beginning at the left.
  - Keep Configuration in a separate right-side panel.

- [x] **T07 — Make manual driver position functional**
  - Add manual driver X/Y/Z controls.
  - Feed them into geometry in Fully Manual and Driver Position Fixed modes.
  - Recalculate immediately when a manual coordinate changes during Run.

- [x] **T08 — Preserve calibration safely across the new states/modes**
  - Do not silently activate an incompatible camera profile.
  - Guided single-camera calibration prepares the required driver and road feeds.
  - Returning from calibration restores a clear state and status.

- [x] **T09 — Add regression tests for the mode/state policy**
  - Test which camera source each mode requires.
  - Test Run/Standby/Stop calculation policy.
  - Retain existing calibration/detection tests.

- [x] **T10 — Validate the redesigned application**
  - Compile all source and tests.
  - Construct the main window off-screen.
  - Run automated tests.
  - Record any physical-camera checks that still require the user’s hardware.

## Validation record — 2026-10-03

- `py -m compileall -q glare_tracker tests`: passed.
- `py -m pytest -q`: **11 passed**.
- Off-screen `MainWindow` construction, event processing, and shutdown: passed.
- Automated session regression covers Run → Standby → Run → Stop in Fully Manual
  mode and confirms that Standby freezes calculation updates.
- Automated source-switch regression confirms that a manual driver coordinate is
  cleared before entering a driver-camera mode.
- Still requires the project hardware: confirm that Standby keeps each selected live
  preview open, Stop releases all camera devices, and Single/Stereo selection displays
  the correct one/two road feeds with the actual configured cameras.

## Accuracy work that follows the UI redesign

- [ ] **A01 — Split guided calibration into driver-only and road-only workflows.**
- [ ] **A02 — Add multi-distance driver and lamp validation with percentage error.**
- [ ] **A03 — Add intrinsic checkerboard calibration to the operator workflow.**
- [ ] **A04 — Add camera-to-windshield extrinsic calibration.**
- [ ] **A05 — Replace single-camera lamp-size ranging for general use with validated
  stereo or an independent depth sensor.**
- [ ] **A06 — Add timestamped CSV/video evidence for accuracy and latency.**

The A-series items are measurement-development tasks. The UI must describe the current
single-camera distance as an estimate and must not present it as general real-world
headlight ranging.
