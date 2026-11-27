# GlareTracker Functional Test Plan

Reviewed: 2026-11-27. Use the updated source (`py -3.13 run.py`) or a newly built
standalone containing the updated guides. Old executables are unchanged.

This is a current operator checklist, replacing the earlier single-road-camera
bring-up instructions. Record PASS, FAIL or NOT TESTED with the date, operator,
saved paths and evidence. Historical hardware results remain in the validation plan;
they are not passes for a newly assembled rig.

Read the [complete offline manual](../../assets/calibration/offline_manual.html)
before calibration. These checks supplement its detailed steps.

## 1. Offline preparation and help

1. Install dependencies, face model and USB drivers on the test laptop while online.
2. Open Cameras > Calibration > Calibration guide... and choose Check offline files.
3. Confirm written steps and all pictures appear. Open complete offline manual.
4. Disconnect the network and repeat. Open the bundled checkerboard PDF.
5. Resize the guide; scroll through every relevant tab and its pictures.

Pass: local instructions/images/manual/PDF remain usable, no required download or
automatic website opening occurs, and missing files give actionable recovery text.
Videos are optional online references. A local-file pass does not test USB hardware.

## 2. Three camera identities and modes

1. Select Stop. Close other apps using cameras and refresh discovery.
2. Choose Fully Auto in Operation > Operating Mode; expand the collapsed panels.
3. Assign Driver, Road left and Road right to three different physical cameras.
4. Use Standby and briefly cover each lens to identify the preview; return to Stop.
5. Verify the role-relevant calibration commands in each operating mode.

Pass: all required feeds are correctly identified and no two live roles share a
device. Do not assume that a historical camera index still identifies the same lens.
Fixed-source modes legitimately expose fewer camera calibration stages.

## 3. Road and driver lens calibration

1. Follow the flat-board preparation, measured square size and varied captures.
2. Collect at least 15 accepted LEFT views and fit; repeat RIGHT.
3. With cameras rigid, collect at least 15 accepted stereo pairs and fit.
4. Check baseline against the physical lens-centre measurement; Save stereo profile.
5. Calibrate the driver camera separately and Save camera profile.
6. Confirm each saved-success message and saved status; close the dialogs.

Pass: actual native frame sizes match for stereo; every fit passes its quality
gates and saving succeeds. A Fit message alone is not a saved profile or physical
accuracy result. Follow rejection messages; do not relax gates to obtain a pass.

## 4. Driver distance: choose the truthful route

Without a commissioned controller: explicitly Skip ToF for now, close its dialog,
leave Driver > Driver Distance > Live driver distance OFF, and enter the independently
measured Fixed distance. Hold the eye plane at that depth during the test.

With commissioned bridge v1: follow the [ToF guide](../guides/TOF_SENSOR_OFFLINE_SETUP_GUIDE.md).
Capture three fit plus two new validation distances, independently measure both signed
offsets, save, dismiss the alert and Close. Deliberately select live distance.

Pass: the indicated route matches what is really connected. Wrong sensor identity,
stale readings or a failed connection must not activate a saved ToF profile. Reuse
on a changed COM port requires Connect / reconnect and fresh valid same-sensor
evidence before Use saved ToF profile.

Current limitation: no controller firmware build is supplied by this repository.
Software tests do not commission a real sensor.

## 5. Installed rig and LCD registration

1. Fix final cameras, focus, filters and panel mounts.
2. BEFORE opening Installed rig + LCD, select Extend, the correct Target display
   and measured active width/height. Choose Fully Auto if all three poses are wanted.
3. Follow the marked first-inner-corner/level-board procedure. Per required camera
   role, capture six fit placements over at least three depths and three new validation
   placements. Fit / validate installed pose. The filtered board must remain visible.
4. Complete all nine independent physical LCD dot measurements and validate mapping.
5. Save installed rig profile, dismiss its alert, then Close the window.
6. Check physical camera order/mounts and confirm them in the parent panel.

Pass: the saved rig is compatible with the actual profiles, camera indices, panel and
selected display. The scene shows Driver, Road L and Road R at their saved positions
in Fully Auto. RIGHT is derived from LEFT plus stereo, not manually invented.
Closing before Save loses unsaved dialog work; display/settings changes require a new
compatible installed calibration.

## 6. Independent geometry and output check

1. Hold a measured eye reference and a diffused stationary lamp at known positions.
2. Independently locate their line's crossing on the panel and compare spot centres.
3. Repeat for both eyes, multiple lamps/depths, centre and edges.
4. Record signed X/Z error and error magnitude in mm, not only screenshots.
5. Run the dedicated physical intersection/LCD/latency protocols for research results.

Pass criteria come from the research protocols. Smooth previews, low reprojection
error, three plausible camera markers and passing automated tests are not substitutes
for these measured results.

## 7. Run / Standby / Stop and failure recovery

1. With the intended setup ready, use Standby to check all required real feeds.
2. Run: confirm output opens only on the selected secondary display.
3. Standby and Stop: confirm that output releases the secondary display.
4. With the rig stationary, test Stop then Run; inspect restored feeds.
5. Test disconnection/reconnection under the project recovery protocol.
6. Close during capture/fitting only when the dialog allows camera/thread release.

Pass: no stale blocking output, hung threads or silent use of invalid measurements.
A rejected calibration, empty sample buffer or missing device remains a clear failure,
with a usable retry/skip route. Record hardware recovery behavior separately.

## 8. Save, restart and transfer

1. Close the app and back up the entire calibration folder including evidence.
2. Reopen with unchanged devices/mounts; verify saved indicators and camera markers.
3. Confirm mounts after checking them; no physical confirmation is assumed on restart.
4. Recheck fixed/live distance choice and output display before Run.

Source profiles are in the workspace's calibration folder. The updated standalone
uses `%LOCALAPPDATA%\GlareTracker\calibration`. Transfer is manual: back up both
locations before copying; no automatic migration or overwrite is performed.
The earlier standalone may have written temporary extraction files.

Pass: matching saved files restore without changing their contents. Changed monitor
name/resolution, panel dimensions, camera identity or lens/stereo fingerprints invalidate
affected saved geometry. Never force old coordinates onto a changed rig.

## Automated and physical evidence

The current suite covers geometry, detection/tracking, mode/state policies,
calibration quality/failure paths, sensor parsing/freshness/identity, persistence,
saved three-camera scene restoration, offline resources and small-window guide layout.
Record the final suite count in PROJECT_STATUS.md.

Physical accuracy, final-filter optical performance, ToF commissioning and the
complete new rig still require the tests above. Mark them NOT TESTED until measured.
