# Driver and installed-rig calibration

Updated 2026-11-26. This describes the development source, not a new standalone release.
The procedures also appear inside the calibration dialogs. Your VL53L0X currently
has no controller connected; use **Skip ToF for now** to test the camera separately.

## Stable driver distance and the toolbar centre button

1. Open **Driver > Driver Distance**. Leave **Live driver distance OFF** for the current
   no-controller bench setup. Set **Fixed distance** to your measured driver-camera
   optical-axis distance to the eye plane; the initial value is 50 cm. Stay at that
   distance. Eye position tracking and optional drowsiness landmarks continue updating.
2. OFF bypasses jittering IPD/PnP range estimates and does not open a ToF connection.
   It uses a declared reference, not a measured distance. The fixed field is editable;
   ON grays it out and restores live camera IPD or selected calibrated ToF.
3. In a camera-based preview, choose Run, wait for fresh eyes and click **Calibrate
   Center**. X/Z recenter immediately and both-eye separation stays intact. A status-bar
   message confirms the action. Distance is preserved. This is preview centering, not
   checkerboard or installed-rig calibration.
4. The button is disabled when eyes are missing/stale, outside Run, in manual-driver
   modes, during LCD testing, or when installed coordinates are active. Hover to read
   the reason. Installed coordinates must use the third calibration dialog instead.

Distance mode and the fixed value persist across restarts. Changing them resets the
preview reference and rejects old queued frames. A selected live ToF that fails never
silently falls back to IPD. Explicit Skip ToF uses IPD only when live distance is ON;
with it OFF, the fixed reference is used instead. If the camera lacks intrinsics,
unprojection remains an approximate preview and live IPD is unavailable.

## 1. Choose the mode, then open Cameras > Calibration

Settings start collapsed. Select the Camera icon, then click the Calibration header
(or focus it and press Space/Enter) to reveal its buttons. Expanded settings now have
more spacing; Driver, Road lights, Geometry and Research use profile, bulb, monitor
and microscope icons respectively.

Road preview check: both panes show the full raw image with equal canvas sizing and
aspect-preserving letterboxing. Read each camera's raw pixel dimensions above its
pane. LEFT may be a frozen last view while RIGHT is live; different board poses at
those stages cannot be used to compare zoom. Compare the same stationary board in the
paired stage instead. Equal resolutions do not guarantee equal focal length/FOV.
Native mode mismatches are rejected rather than hidden by rescaling. The dialog body
scrolls on smaller screens while capture/fit/save/close actions remain accessible.

| Mode | Component calibration buttons | Installed rig calibration |
|---|---|---|
| Fully Auto | Road stereo and driver camera/ToF | Road LEFT pose, driver pose, LCD mapping |
| Driver Position Fixed | Road stereo | Road LEFT pose and LCD mapping; enter measured eyes manually |
| Headlight Position Fixed | Driver camera/ToF | Driver pose and LCD mapping; enter measured lamps manually |
| Fully Manual | Neither camera component | LCD mapping; manual geometry can also use nominal panel dimensions |

Driver and installed-rig calibration stop live tracking before using a camera.
Road stereo retains its existing requirement to select Stop first. Wait for camera
discovery to finish. Close any other application using the webcams.

## 2. Driver camera, independently of ToF

1. Open **2. Driver camera and ToF calibration** and its **Camera and ToF guide**.
   The guide has separate ordered Camera and ToF tabs.
2. Print the supplied A4 board at 100%, measure its squares, and attach it to rigid,
   completely flat backing. The pattern has 9 x 6 inner corners / 10 x 7 squares.
3. Enter the measured square side. The supplied PDF uses 2 cm squares. The IPD field
   defaults to a 6.3 cm estimate; measure the participant's separation for IPD testing.
4. Start the driver preview. Capture at least 15 sharp views covering the image,
   several distances, and gentle tilts. Move the board; keep final camera focus fixed.
   Very similar views are rejected. Reset captured views if the target/setup was wrong.
5. **Fit camera**, inspect the intrinsic RMS and actual image size, then explicitly
   **Save camera profile**. A fit alone does not activate a profile. Save shows a
   success alert. The existing saved profile survives a failed retry.
6. With no controller, select the ToF tab and **Skip ToF for now**. Its indicator says
   skipped. Camera calibration and sensor calibration have separate skip controls.
   **Use saved ... profile** reverses a skip without forcing a new calibration.

The driver preview is mirrored for convenience during tracking; calibration and
measurement pixels stay native and unmirrored. Calibration and live capture request
the same driver-camera mode. A changed actual frame size invalidates reconstruction.

## 3. ToF, after a controller is assembled

1. The host expects the [bridge v1 protocol](../reference/TOF_BRIDGE_PROTOCOL.md).
   Controller firmware and physical wiring are still outstanding. A sketch printing
   one distance number per line cannot supply the required identity, quality and times.
2. Mount the sensor close to the driver camera with parallel forward axes. Fix its
   position. This first fusion model assumes a centred, near-frontal face; it does not
   solve arbitrary sensor-to-camera rotation or identify which object returned light.
3. Choose its COM port and Connect. Only actual synchronized valid packets are accepted.
4. Use a stable flat target that fills the sensing area. Measure from the sensor's
   reference surface. Capture 20 stable readings at each of three distinct **fit**
   distances and two additional **validation** distances spanning the seating region.
   Example sequence: fit 30/50/70 cm, validation 40/60 cm. Do not reuse distances.
5. Enter the signed sensor-to-camera Z offset in the camera's forward direction.
   Separately measure the facial surface-to-eye-plane Z correction. Confirm both;
   do not invent a zero offset. Target capture calibrates range bias, not human eyes.
6. **Fit and Save ToF** fits bias from fit samples only and checks the separate validation
   samples. A success alert records only that range-profile check. Reset samples if
   references or sensor identity were wrong; previous saved profiles remain intact.
7. Independently compare fused eye depth with measured truth on the final mount,
   including glasses and incoming glare. A single-zone return can come from a hand or
   background. No pupil depth or drowsiness claim follows from a range fit alone.

Live depth is approximately `raw range + bias + sensor Z offset + eye-plane correction`.
The first model accepts head pitch/yaw within 10 degrees and an eye midpoint within
5 degrees of the camera axis. It requires a compatible sensor identity and fresh
range paired with the camera observation. Invalid ToF clears the measured output;
it never silently falls back to IPD. With live distance ON, explicit Skip ToF selects
the IPD bench estimate. With live distance OFF, the entered fixed reference is used.

## 4. Installed rig: the third calibration

```text
Driver (-Y)       LCD plane Y=0         Road (+Y)
driver cam <---   | active panel |   ---> road LEFT + RIGHT
ToF        <---   |              |

Origin = bottom-centre of active pixels; X lateral, Z up; all distances in cm.
```

Positive X means the driver's right while looking through the LCD toward the road.
Measure all camera/board coordinates using that one convention, including when
standing on the opposite side of the rig.

The permanent cameras keep facing their subjects. They do not look at the LCD.
Finish component calibration first, install the final optics, and freeze the rig.
Optical filters must pass geometric verification before measurement claims.

1. Open **3. Installed rig / camera-to-LCD calibration**. Confirm which physical
   device is road LEFT, road RIGHT and driver; name the mount revision.
2. Use a temporary rail/square stand to place a rigid checkerboard at measured 3D
   positions on the side the camera sees. Its origin is the **first inner corner**,
   not the paper edge. Free-hand waving is insufficient at this stage.
3. Road LEFT: enter the measured first-corner XYZ and board rotations. With zero
   rotations, corner columns progress along LCD +X and rows down -Z; road Y is positive.
   Capture six distinct **fit** placements across at least three Y depths. Then capture
   three different **validation** placements. Fit the installed pose.
4. Driver: repeat on the driver side with negative Y. At zero rotation, columns progress
   along LCD -X and rows down -Z. Prefer measured parallel placements with all rotation
   entries zero. If tilted, measure right-hand rotations around LCD X/Y/Z; composition
   is `Rz * Ry * Rx`. Do not estimate rotations by eye.
5. After a capture the preview freezes with corner **1** marked. Compare it with the
   physically marked corner. Use Undo if wrong; Resume preview before the next capture.
   Reverse corner order handles a 180-degree checkerboard-detection ambiguity.
6. Road RIGHT is related to LEFT through the saved stereo geometry; it needs no
   separate LCD pose fit. Its rigid placement and calibrated LEFT/RIGHT order matter.
7. Select the actual secondary LCD under Prototype Display Output in Extended Desktop
   mode. In LCD Mapping, **Show mark** for each of the six fit targets, measure the
   mark's X/Z from the active-area bottom-centre, confirm and Capture. Repeat for the
   three separate validation targets, then Fit. Do not copy computed positions as truth.
8. Save the installed rig after all required fits pass. A success alert confirms saving.
   The profile records camera calibration fingerprints, selected LCD/mode and dimensions.
9. Return to Calibration and confirm the camera identities/order and unchanged mounts.
   This confirmation is per launch because cheap webcam indices can change. Run then
   applies compatible poses; it does not recenter measured eyes using the demo offset.

Changes to camera selection, intrinsic/stereo calibration, selected display mode or
panel dimensions invalidate the relevant binding. Remounting/refocusing must be
reported by the operator; software cannot physically detect every mount change.

### Reading the camera rig in the 3D view

After saving the third, installed-rig calibration, compatible saved camera poses
appear automatically. You should see Driver, Road L and Road R when both driver and
road roles have accepted profiles. Their optical-centre points use the same centimetre
coordinates as the LCD plane; arrows show camera viewing direction. They do not depict
measured camera-body size or lens field of view. RIGHT is positioned/oriented through
the saved stereo R/T, not by guessing half the baseline from a manual camera position.

Hover over the rig-status text at the bottom of the scene to read X/Y/Z coordinates.
In 3D view settings, Camera positions hides/shows the markers. Saved poses awaiting
mount confirmation are identified separately; confirm camera order and unchanged
mounts before Run. Changing the selected cameras, their calibration, panel dimensions
or display invalidates affected saved markers. If calibration is incomplete, the scene
keeps an explicitly uncalibrated/demo reference instead of inventing real positions.

Lens/stereo fitting alone does not establish camera-to-panel locations. Finish the
installed-rig workflow, then independently verify physical intersections. The example
image in the thesis reference uses synthetic test poses and is marked OFFLINE EXAMPLE.

## 5. What passes, and what still needs measurement

These are prototype defaults declared before fitting, not established thesis accuracy:

| Check | Software limit |
|---|---|
| Driver intrinsic fit RMS | <= 1.5 px |
| Installed pose fit and held-out RMS | <= 1.5 px each |
| Held-out known point to observed ray, transverse distance | <= 2 cm maximum |
| Held-out measured LCD marks | <= 0.3 cm maximum |
| ToF target readings | >= 20 per distance, standard deviation <= 1 cm |
| ToF held-out median corrected range | <= 2 cm error |

Pose validation checks ray agreement; it does not independently validate depth along
the ray. For real accuracy, use independently measured eyes and lamps, both eyes,
multiple lights and depths, panel edges, and the final filters. Record actual spot
error and latency using the existing physical protocols. A saved-profile alert does
not establish an end-to-end accuracy or optical attenuation result.

The physical-output watchdog clears camera-derived spots for missing, incompatible,
old or poorly paired observations. Current limits are 200 ms camera receipt age,
50 ms camera-pair/readout skew and 100 ms range age. Ordinary webcams provide host
readout times rather than synchronized exposure timestamps; these checks do not prove
hardware synchronization or external photon-to-LCD latency.

References: [OpenCV camera calibration and pose conventions](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)
and [ST VL53L0X datasheet](https://www.st.com/resource/en/datasheet/vl53l0x.pdf).
