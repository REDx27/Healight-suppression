# Road Stereo Chessboard Setup Guide

Updated: 2026-11-03. Current development priority: bring up the two road cameras
before adding live driver tracking back into the experiment. This is a stationary
laboratory procedure, not a moving-vehicle test.

## 1. Fix the physical setup first

- There are **two road cameras plus one driver camera**, confirmed by the operator.
- On the 2026-11-03 live probe, the integrated driver camera was index **1** and the
  external road cameras were indices **0** and **2**. Confirm the previews after every
  reconnect because Windows can reorder them.
- Mount the road cameras rigidly, side by side, with overlapping views. As you look
  toward the scene from behind the cameras, primary is LEFT and secondary is RIGHT.
  The supported matcher expects a horizontal left-to-right pair.
- Measure and record optical-centre separation; do not assume the old 25 cm default.
- Begin this initial guided pass **without the sunglass filters**, as instructed by
  the dialog. After a passing stereo profile is saved, fix and label each filter
  without moving either camera. That bare-camera result is provisional until the
  planned post-filter geometric verification passes. If a filter changes effective
  geometry beyond the declared limit, repeat full calibration through the filters
  using a brighter or backlit target.
- Lock focus/zoom using the device's supported controls or camera utility. The app
  does not currently lock autofocus. Changing focus, zoom, lens/filter placement or
  either mount requires recalibration. Exposure may be adjusted for board visibility,
  but avoid clipped whites, blurred frames and disappearing dark squares.
- Photograph the mount and label the cameras. Device indices are not persistent
  hardware identities: check the feeds again after unplugging/reordering devices.

## 2. Prepare the chessboard

Use a flat black-and-white checkerboard with a white outer margin, firmly attached
to a flat backing. The default is **10 columns × 7 rows of squares**, giving
**9 × 6 inner corners**. Enter inner corners, not square counts.

Measure the printed side of one square with a ruler; enter that size in centimetres.
The default 2.5 cm is only a starting value, not an assumed property of your print.
Measure across several squares and divide to reduce ruler error. Printer scaling
changes metric depth, even when the fitted reprojection error is low.

The corner convention, intrinsic fitting, stereo fitting and rectification follow
the [OpenCV calibration documentation](https://docs.opencv.org/4.5.2/d9/d0c/group__calib3d.html).

## 3. Capture and fit

1. Launch `py -3.13 run.py` and select **Stop**. Close other apps using the cameras.
2. Refresh the available cameras and wait for scanning to finish. Choose **Driver
   Position Fixed** and **Stereo Cameras**. Assign the left and right road feeds to
   Headlight camera and Headlight camera 2. Leave the driver camera assigned but idle.
3. After discovery, choose **Calibrate now** in the startup offer, or click
   **Calibrate road stereo (chessboard)** later. Confirm indices, inner-corner counts
   and measured square size.
4. Complete the three stages in order: collect at least 15 varied LEFT-only views and
   fit LEFT intrinsics; repeat independently for RIGHT; rigidly fix both cameras and
   then collect at least 15 paired views visible in BOTH feeds. Move the board, not
   the cameras. Cover different tilts, distances and positions, including image edges
   and centre. Avoid nearly identical images, blur or obscured corners.
5. The application saves only pairs where both boards are detected, rejects near
   duplicates, and preserves raw capture images without display scaling or mirroring.
   Both road cameras use the measured stable shared mode of **320 x 240 at 15 FPS**.
   At 640 x 480, one stream opened and grabbed but returned no frames when both road
   cameras shared the USB root hub.
6. Fit each stage when enabled. The paired fit holds the accepted individual
   intrinsics fixed. A stereo candidate passes the software gates only if its
   matrices are finite, stereo RMS is at most 1.5 px, the 95th-percentile rectified
   vertical corner error is at most 2 px, and the horizontal baseline has the expected
   sign. These are initial engineering gates, not a proven physical accuracy limit.
7. Compare the reported baseline with your ruler measurement. If inconsistent, do
   NOT save: check units, board size, camera order and pose diversity; capture again.
8. Save an accepted profile, close the dialog, then install the dark filters without
   moving the cameras. The current software warns that post-filter verification is
   still required; do not collect final measurement evidence until that gate is
   implemented and passed. No active profile is replaced until you explicitly save.

Ordinary USB camera grabs are sequential, **not hardware-synchronized**. Keep the
board and later test light still during initial tests. Timing for moving targets
requires separate validation. A low fit error uses the same images as calibration;
it is not held-out accuracy evidence.

## 4. Fine-tune one stationary light

Keep Driver Position Fixed and one light source initially. Use the two **Original**
previews to confirm the same lamp is visible and not badly saturated. Then use
Detection overlay, Threshold mask and other processing views to tune the existing
brightness, exposure, area and confidence controls. Camera-driver settings may not
be supported equally by both webcams; visually inspect both feeds.

Use an isolated torch or phone light inside both views. Do not aim the road pair at
the room's fluorescent tube: the live diagnosis showed both feeds dominated by a long
saturated ceiling strip instead of a point-like test source. The detector now rejects
edge-truncated and strongly elongated saliency candidates, but scene preparation is
still necessary.

Before calibration, the status may show **ROUGH UNCALIBRATED** when one candidate in
each feed can be paired. This is an alignment/tuning aid only: its displayed depth is
assumed, and it cannot produce windshield intersections, valid measurement records or
LCD output. A feed showing vertical color bars is now marked invalid; replug that
camera, select Stop, and Run again before continuing.

Read the stereo diagnostics:

- **Calibration required / previews only:** profile missing, wrong camera order,
  invalid fit, or resolution mismatch. The app intentionally emits no metric light
  coordinates; the old 900 px focal / 25 cm baseline fallback is removed.
- **Left > 0, Right = 0** (or the reverse): investigate visibility, filter darkness,
  saturation, focus, threshold and candidate filtering in the missing view.
- **Both > 0, Matches = 0:** check common lamp identity, camera order, calibration
  and disparity. Matching requires positive disparity and vertical error ≤3 px.
- **Matches > 0:** record range, then compare with independent ruler measurements.
  A match does not by itself prove accuracy; multiple lights can be ambiguous.

Check a stationary lamp at several measured depths and lateral positions, with
repeated runs. Compare reported depth with distance along the calibrated rig's
forward axis, not slant distance or distance from an arbitrary laptop location.
The live coordinate mapping still assumes a centred, aligned rig; camera-to-windshield
extrinsic profiles are NOT yet applied. Do not claim accurate windshield intersections
from stereo calibration alone.

After stereo is repeatable, switch to Fully Auto to include the driver camera. Then
resume the recording soak and the ordered ground-truth/extrinsic/physical protocols.

## Evidence and limitations

- Each attempt is preserved under `calibration/stereo_sessions/<UTC-session>/`:
  `setup.json`, LEFT/RIGHT individual images and reports, paired raw
  `NNN_left.png` / `NNN_right.png`, `report.json` after stereo fitting, and
  `accepted_calib.npz` after saving. Abandoned attempts remain available.
- The active profile is `calibration/stereo_<left-index>_<right-index>_calib.npz`.
  Legacy generic `stereo_calib.npz` files are not automatically applied. Recalibrate
  through this workflow; an unlabelled profile cannot establish camera identity.
- Raw sessions and active calibration files are ignored by Git. Back them up
  separately with setup photographs, actual device/filter identities, measured
  baseline, held-out distance results and the source commit used.
- Automated tests cover synthetic geometry and mocked camera/UI paths. The physical
  chessboard capture, real camera drivers, true range accuracy and synchronization
  still require operator validation. No physical test is marked passed by this guide.
