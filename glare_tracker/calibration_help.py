"""Offline operator instructions; shared by the app and the printable HTML manual."""
from html import escape
from pathlib import Path
import sys

from glare_tracker.operating_modes import OperatingMode, policy_for

ASSET_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "assets" / "calibration"
IMAGE_WIDTH_TOKEN = "__GUIDE_IMAGE_WIDTH__"
GUIDE_SOURCE_FIGURES = ("flat_board.svg", "pose_coverage.svg", "stereo_sequence.svg", "stereo_capture.svg",
                        "offline_workflow.svg", "rig_coordinates.svg", "tof_wiring.svg", "tof_offsets.svg")
GUIDE_IMAGES = ("offline_workflow.png", "flat_board.png", "pose_coverage.png",
                "stereo_capture.png", "rig_coordinates.png", "tof_wiring.png", "tof_offsets.png",
                "camera_rig_example.png")
VIDEO_REFERENCES = (
    ("Camera Calibration with MATLAB — MathWorks", "https://www.mathworks.com/videos/camera-calibration-with-matlab-81233.html",
     "Watch how the checkerboard is moved. MATLAB buttons differ from GlareTracker. The publisher hosts the video and transcript."),
    ("OpenCV Python Camera Calibration — Kevin Wood", "https://www.youtube.com/watch?v=H5qbRTikxI4",
     "The creator demonstrates board capture and camera parameters. Do not run his scripts instead of this app."),
    ("JP's Product Pick: VL53L0X distance sensor — Adafruit", "https://www.youtube.com/watch?v=VxnrHCuABSk",
     "Sensor introduction only: its breakout and demo firmware are different from your module and bridge protocol."),
)


def guide_image(name, alt):
    path = ASSET_ROOT / name
    if not path.is_file():
        return f'<p><b>Local picture missing: {escape(name)}.</b> Use the written steps; restore the complete app folder before the trial.</p>'
    return (f'<p><img src="{escape(path.as_uri(), quote=True)}" width="{IMAGE_WIDTH_TOKEN}" '
            f'alt="{escape(alt, quote=True)}"></p>')


def video(index):
    title, url, purpose = VIDEO_REFERENCES[index]
    return f'<p><b>Optional online video:</b> <a href="{url}">{escape(title)}</a>. {escape(purpose)} Internet is required; no step below depends on watching it.</p>'


OFFLINE_STEPS = """
<h2>Before you leave the internet connection</h2>
<p><b>Do this once on the actual laptop you will use at the bench.</b> All written instructions and pictures in this guide are local. Videos are optional online references, not downloaded videos.</p>
<ol><li>Copy the <b>whole application folder</b>, not only run.py. Keep assets/calibration, assets/icons, the supplied chessboard PDF, and the calibration folder. If using the standalone app, use a build containing these updated guides; an older EXE will not gain new source changes.</li>
<li>Install the app's Python dependencies and required USB/COM drivers while online. Open the app once. Check every camera in <b>Standby</b>, then choose <b>Stop</b>. MediaPipe's face model must already be in assets; it is not fetched at the bench.</li>
<li>Open <b>Calibration guide...</b>, visit every relevant tab and confirm pictures appear. Use <b>Open complete offline manual</b> to open the printable local manual. Print that manual or keep its self-contained HTML file on a second device.</li>
<li>Print the bundled A4 checkerboard at <b>Actual size / 100%</b>. Have a ruler, rigid flat backing, tape, board stand, and a way to measure board positions without moving the cameras. Measure squares after printing.</li>
<li>If using ToF, prepare the exact controller firmware, its programming tools/libraries and USB driver before leaving. <b>This repository does not yet include the bridge firmware.</b> If these are unavailable, plan the fixed-distance camera-only route in the ToF tab.</li>
<li>Disconnect Wi-Fi/network. Reopen the app and this guide. Reopen saved calibration if available. Check images, the PDF and USB devices again. This is the offline rehearsal; fix missing files or drivers now.</li></ol>
<h3>Save your work safely</h3>
<p>After calibration, close the app before copying the entire calibration folder as a backup, including evidence subfolders. In source mode it is beside run.py. The updated standalone Windows app uses <b>%LOCALAPPDATA%&#92;GlareTracker&#92;calibration</b> (paste this into File Explorer's address bar). Record the displayed saved path too.</p>
<p><b>Moving from source to standalone:</b> there is no automatic profile migration. With both apps closed, back up any destination calibration folder, then have the team copy the source calibration folder's contents and evidence into the standalone location above. Keep both backups; do not overwrite a newer calibration blindly. Reopen, verify device/display bindings and confirm the physical mounts. An old one-file EXE may have saved into temporary extracted files; those are not guaranteed to survive its exit. Recalibrate if the original files are unavailable.</p>
<p><b>Stop rule:</b> if an essential picture, PDF, camera or driver is missing, restore it before measurement. Do not assume a green preview or a Fit message means a saved, accurate calibration.</p>
<h3>Words used in this guide</h3>
<p><b>Lens / intrinsic calibration:</b> teach the app how each camera turns a scene into pixels, including lens distortion.
<b>Stereo calibration:</b> teach it the relationship between the two road cameras.
<b>Baseline:</b> distance between their lens centres.
<b>Installed pose:</b> a camera's position AND viewing direction relative to the LCD.
<b>LCD mapping:</b> link measured centimetres on the panel to output pixels.
<b>Validation / held-out:</b> check new measured positions that were not used to calculate the fit.
<b>Save:</b> keep an accepted result on disk for the next launch. 10 mm = 1 cm.</p>
""" + guide_image("offline_workflow.png", "Calibration order and independent optional ToF route")

ROAD_STEPS = """
<h2>1. Calibrate the two road cameras</h2>
<p><b>Goal:</b> save each lens model, then the relationship between the two cameras. This does not yet locate them relative to the LCD.</p>
<ol><li>Choose <b>Stop</b>. Wait for scanning to finish. Close Windows Camera, Teams and other camera apps. Label the physical webcams LEFT and RIGHT; a USB index can change after reconnection.</li>
<li>Select the camera icon in Properties. Expand <b>Camera Selection</b>. Assign <b>Driver</b> to the laptop camera and <b>Road left</b>/<b>Road right</b> to the external pair. In Standby, briefly cover each lens to identify its preview, then return to Stop. Do not identify cameras by index alone.</li>
<li>Remove dark filters for lens/stereo fitting. Keep camera focus unchanged. Expand <b>Calibration</b>, click <b>1. Road stereo calibration</b>, then <b>Print A4 chessboard...</b>.</li>
<li>Mount the print on a completely flat rigid board with its white border visible. Count <b>9 by 6 INNER corners</b> (10 by 7 squares). Measure five adjacent square widths, divide by five, then convert mm to cm. Example: five squares = 100 mm, so one square = 20 mm = <b>2.000 cm</b>. Enter the measured size, not an assumed value.</li>
<li>Click <b>Start LEFT calibration</b>. Hold the board still, keep the entire pattern visible and click <b>Capture LEFT view</b>. Wait for the saved count to increase. Rejected/similar views do not count.</li>
<li>Collect at least <b>15 accepted views</b>: about five central views at different distances, five covering edges/corners, five gently tilted. This is a pose checklist, not permission to reuse identical pictures. Images must be sharp and the squares large enough to see.</li>
<li>Click <b>Fit LEFT intrinsics</b>. Wait. A pass advances to RIGHT; repeat steps 5–6 using <b>Start RIGHT calibration</b>, <b>Capture RIGHT view</b>, and <b>Fit RIGHT intrinsics</b>. Both native resolutions must match. A slight difference in apparent zoom at equal resolution can reflect separate lenses; do not resize the captures yourself.</li>
<li>For stereo, rigidly fix both cameras. Measure between lens centres, not case edges: e.g. <b>15.35 cm</b>. Put the board on a stand in the shared view. Click <b>Start STEREO calibration</b>. Move the board between positions; let it stop before <b>Capture pair</b>. Collect at least 15 accepted pairs across distances, image regions and gentle tilts. Keep BOTH camera mounts fixed.</li>
<li>Click <b>Fit stereo geometry</b>. A passing fit enables <b>Save stereo profile</b>. Check its reported baseline against the ruler. Example: 15.43 cm vs measured 15.35 cm is a 0.08 cm difference; record it and assess against your measurement uncertainty. This is not a universal acceptance tolerance.</li>
<li>Click <b>Save stereo profile</b>. Wait for <b>CALIBRATION COMPLETE — STEREO PROFILE SAVED</b> and the saved confirmation. Only then close.</li></ol>
<h3>When to stop and retry</h3>
<p>RMS means the average mismatch between predicted and observed picture points, measured in pixels (px). The individual lens gate is 1.5 px; stereo must also pass its separate row/order checks shown in the window. A low RMS alone does not prove physical accuracy.</p>
<p>If no camera opens, close other camera apps, reconnect the same USB ports, recheck roles and use the retry button. If a fit fails, do not loosen quality thresholds: check board flatness, blur, repeated views and camera order. If bad paper was used, close and restart with a correct board. After adding filters, keep the mount fixed and verify known lamp positions before research measurements.</p>
""" + guide_image("flat_board.png", "Good rigid flat target compared with bent or loose paper") + guide_image("pose_coverage.png", "Accepted calibration pictures need varied distances positions and gentle tilts") + guide_image("stereo_capture.png", "Both road cameras see the same stationary board in their overlapping views") + video(0)

DRIVER_STEPS = """
<h2>2A. Calibrate the driver camera</h2>
<p><b>Goal:</b> save the driver lens model. Its physical location is measured later in Installed rig + LCD. The tracking preview may be mirrored; calibration uses the original, unmirrored image.</p>
<ol><li>Choose Stop, verify the physical <b>Driver</b> camera selection, expand <b>Calibration</b> and open <b>2. Driver camera + ToF</b>. Select <b>1. Driver camera</b>.</li>
<li>Enter the measured square side in cm, using the same flat 9 by 6 inner-corner board. Example: 20 mm = 2 cm. Keep the final camera focus and image mode fixed.</li>
<li>Click <b>Start camera</b>. Use <b>Capture view</b> for at least 15 accepted sharp views covering centre, edges, corners, near/far and gentle tilts. Move the board between captures and pause. The saved counter must increase.</li>
<li>Click <b>Fit camera</b>. Wait for <b>FIT PASSED</b>, inspect RMS/image size, then click <b>Save camera profile</b>. The fit is NOT saved until this click and its success confirmation.</li>
<li>If the fit fails, follow the message. Reset wrong captures with <b>Reset captured camera views</b>; restart if the board or image mode was wrong. Do not overwrite a good saved profile with a failed fit.</li>
<li>Move to the separate <b>2. ToF sensor</b> tab. Follow its hardware-ready route OR choose <b>Skip ToF for now</b>. Camera and ToF skips are independent; Skip never means Calibrated.</li></ol>
<h3>Usable bench route without a ToF controller</h3>
<ol><li>Skip ToF explicitly and close the dialog. Select the profile-shaped <b>Driver</b> icon, expand <b>Driver Distance</b>, and leave <b>Live driver distance</b> OFF.</li>
<li>Measure straight along the camera's viewing direction from its optical reference to the eye plane. Enter <b>Fixed distance</b>: for example 52.0 cm after measuring 52 cm. Keep the person at that distance. This number is a measured reference, not automatic range.</li>
<li>The camera still tracks eye movement. Moving forward/backward invalidates your fixed-distance assumption; remeasure or use a commissioned ToF setup. Turning Live driver distance ON while ToF is skipped uses an IPD camera estimate which can jitter.</li></ol>
<p><b>Checkpoint:</b> the camera indicator says calibrated; the ToF indicator truthfully says skipped or calibrated. A fixed reference is acceptable for declared bench testing, but it does not validate changing driver depth.</p>
""" + guide_image("pose_coverage.png", "Move the flat board through the driver image while leaving the camera fixed") + video(1)

TOF_STEPS = """
<h2>2B. Set up the optional ToF sensor</h2>
<p><b>Read this gate first:</b> a VL53L0X board cannot connect directly to USB. You need a controller, appropriate wiring, a data-capable USB cable and compatible <b>GlareTracker bridge v1 firmware</b>. This repository supplies the PC side, not that firmware. A sketch that prints a distance number is incompatible. Do not keep retrying Connect until the controller has been commissioned.</p>
<h3>Route A — no commissioned controller</h3>
<ol><li>Open <b>2. Driver camera + ToF</b> &gt; <b>2. ToF sensor</b>.</li><li>Click <b>Skip ToF for now</b>. Keep the camera calibration; do not skip it by accident.</li><li>Use the measured fixed-distance route in the Driver camera tab of this guide. This route works offline with the existing webcam. Stop here for sensor setup.</li></ol>
<h3>Route B — hardware and bridge have been checked</h3>
<ol><li>Unplug USB before wiring. Identify your module by its printed <b>VIN, GND, SCL, SDA</b> labels; do not assume the header's left-to-right order. For a classic Uno R3/Nano example: SDA goes to A4, SCL to A5, and GND to GND. <b>Verify the exact breakout's supply and logic voltage before connecting VIN.</b> The bare chip, a branded regulated breakout and an unverified cheap module have different requirements.</li>
<li>A technical helper must first load and verify bridge v1, USB driver and sensor identity/timestamps/status. Bring those tools/files offline. A raw sensor demo is only an electrical test; it cannot calibrate with this app.</li>
<li>Fix the sensor near the driver camera, facing the same direction toward the forehead/upper face. It must not look through the LCD. This first implementation assumes near-parallel, near-centred mounting, not arbitrary sensor rotation.</li>
<li>Select <b>USB serial port</b>, e.g. COM5, then <b>Connect / reconnect</b>. COM5 is an example, not a required port. Close Arduino Serial Monitor and any app holding that port. Continue only when synchronized valid readings arrive. A clock/HELLO waiting message is not successful connection.</li>
<li>Use a fixed flat target filling the sensor view, not a face, for range calibration. Measure from the sensor's optical reference. For each row below, enter <b>Measured target distance</b>, choose <b>Sample use</b>, wait for stable readings, then click <b>Capture 20 readings</b>. Confirm a row was accepted before moving the target.</li></ol>
<table border="1" cellpadding="6"><tr><th>Order</th><th>Sample use</th><th>Example true distance</th></tr><tr><td>1 / 2 / 3</td><td>fit</td><td>30 / 50 / 70 cm</td></tr><tr><td>4 / 5</td><td>validation</td><td>40 / 60 cm</td></tr></table>
<p>Use distances spanning the actual seating range. These are example measured target positions, not values to copy when the target is elsewhere. Validation positions must be different from fit positions; they check rather than build the correction. After each capture the buffer clears: wait for 20 NEW stable valid readings at the next position.</p>
<p><b>Two different Z meanings:</b> in this ToF tab, Z means the DRIVER CAMERA's forward direction toward the person. In installed-rig coordinates, world Z means height. Do not enter a height in these offset boxes.</p>
<ol start="6"><li>Enter both independently measured signed offsets. <b>Sensor-to-camera Z offset:</b> positive if the sensor's reference is ahead of the camera toward the face; negative if behind. <b>Surface-to-eye Z correction:</b> add the signed change from the sensed face surface to the eye plane along the same camera-forward direction. It may be positive or negative. Do not copy a generic facial offset.</li>
<li>Example arithmetic ONLY: raw 48 cm + fitted bias 1 cm + measured sensor offset 0.5 cm + measured eye correction -0.5 cm = 49 cm camera-to-eye depth. If your measurements differ, enter yours. Zero means a measured zero, not unknown.</li>
<li>Tick <b>I independently measured both signed offsets</b>. Click <b>Fit and Save ToF</b>. A pass needs three fit and two validation distances, at least 20 fresh valid samples per row, stable samples (standard deviation at most 1 cm), and held-out corrected error at most 2 cm. Wait for the saved confirmation.</li>
<li>Dismiss the save-success alert, then click <b>Close</b> in the driver calibration dialog. Only now return to the parent <b>Driver &gt; Driver Distance</b> panel. Turn <b>Live driver distance</b> ON only for a connected, compatible sensor profile. Keep the face near frontal and central. Independently compare camera-to-eye distance at several positions before recording results.</li></ol>
<h3>Reuse the same saved sensor after reconnecting</h3><p>With its mount and offsets unchanged, select the controller's actual current COM port, click <b>Connect / reconnect</b>, and wait for fresh valid ranges from the same sensor identity. Click <b>Use saved ToF profile</b>. A successful message names the sensor and active port; a changed COM port is saved only after this check. Wrong identity, stale data or a disconnected controller leaves the old profile intact. Replacing the sensor or moving its mount requires new calibration. Dismiss any alert and close this dialog before returning to the main settings.</p>
<h3>Recovery</h3><p>No COM port: check data cable, USB driver and the port list after plugging in. HELLO/clock waiting: firmware or timing is not commissioned; use Route A. Missing/stale/invalid readings: stop the trial, correct the return or connection, and reconnect; never mark this as a passed sensor. Wrong sample distance: use <b>Reset captured ToF distances</b> and recapture all five rows. New sensor or changed sensor mount needs a new profile.</p>
<p>The sensor measures a surface, not a pupil. Hands, hair, glasses and bright ambient light can affect returns. The present fusion accepts a small near-frontal region (head pitch/yaw about 10 degrees, eye midpoint about 5 degrees from the camera axis). Invalid selected ToF does not silently become a valid camera measurement.</p>
""" + guide_image("tof_wiring.png", "Label-based example wiring with module-voltage verification gate") + guide_image("tof_offsets.png", "Signed sensor and eye-plane offsets along the camera forward direction") + video(2)

RIG_STEPS = """
<h2>3A. Locate the installed cameras relative to the LCD</h2>
<p><b>Prepare:</b> save the lens/stereo profiles and fix the final panel/camera mounts. Permanent road cameras face the road; the driver camera and ToF face the driver. They do not need to see the LCD.</p>
<h3>Set the display BEFORE opening the installed-rig window</h3>
<ol><li>On the main app, choose <b>Stop</b>. Select <b>Fully Auto</b> in <b>Operation &gt; Operating Mode</b> if all three cameras will be used.</li>
<li>Connect the final monitor, press <b>Win+P</b> and choose <b>Extend</b>. In Operation, expand Operating Mode and enable <b>Show advanced configuration</b>. Open Research (microscope), expand <b>Prototype Display Output</b> and choose the correct <b>Target display</b>. Turn <b>Use prototype display during Run</b> ON. Keep the operator app on the laptop.</li>
<li>In Geometry (monitor), expand <b>Windshield</b>. Measure the actual lit image width and height, excluding the bezel. Select Custom and enter those measurements if the named preset is different. A diagonal size or pixel resolution is not an active-area measurement.</li>
<li>Install final dark filters without changing focus or moving the camera mounts. The board must still be clearly visible for the following installed-pose captures. Illuminate the target enough to see its corners through the filters. If this is impossible, stop and ask the team for a suitable target/lighting arrangement. Removing filters again does not validate final-filter geometry.</li></ol>
<p><b>Important:</b> the installed-rig window blocks the parent settings and binds to the display, dimensions and camera profiles selected when it opens. Set these first. If they are wrong, close the window and correct them BEFORE any captures; closing discards unsaved pose/mark work. Reopen and start the installed workflow again.</p>
<h3>One origin and one set of signs</h3>
<p>Mark <b>bottom-centre of the active pixel area</b>, not the bezel, as zero. Stand on the DRIVER side looking toward the road when naming left/right. X is sideways: driver-right positive. Y is straight away from the panel: road positive, driver negative. Z is up from the bottom edge. All entries are cm.</p>
<p>Example: first INNER corner 10 cm left, 80 cm roadward, 20 cm up = <b>X -10, Y +80, Z +20</b>. On the driver side the Y value is negative. Measuring paper edges instead of the marked inner corner is wrong.</p>
<h3>Use the simple, level-board route</h3>
<ol><li>Choose Stop. Open <b>3. Installed rig + LCD</b>. Give the rig a revision name (e.g. bench-rig-v1). After physically checking identities/mounts, tick <b>Camera order and mounts checked</b>.</li>
<li>Select <b>1. Road installed pose</b> (this uses Road LEFT). Put a rigid board on a stand in front of that camera. Face its printed side toward the camera. Keep it level and parallel to the panel, using a square/level. At this stage do NOT freely wave/tilt the board as you did for lens fitting.</li>
<li>Mark the first INNER corner. At zero rotations, Road columns run along panel +X and rows down -Z. Thus its first corner is the leftmost/topmost in the fixed driver's coordinate view; from the opposite road side this can look reversed. The DRIVER board uses columns along panel -X and rows down -Z. Never redefine X by where you are standing.</li>
<li>Enter the measured square side and first-corner X/Y/Z. Leave all <b>Measured rotations</b> at 0 only when the board really is level and parallel. If you cannot verify that, stop and get help with a measured jig. Tilted-board angle entry is an advanced procedure, not guesswork.</li>
<li>Select <b>Placement use: fit</b>. Click <b>Start preview</b>, confirm measurements match this view, then <b>Capture measured placement</b>. The picture freezes and marks corner <b>1</b>. Check that it is your physical marked corner. If wrong, <b>Undo last placement</b>, then <b>Resume preview</b>; use <b>Reverse detected corner order (180 degrees)</b> only if needed. Click Resume before every next capture.</li>
<li>Record six distinct fit placements across at least three Y depths. Example planning sheet below is for road-side, level boards; use it only if these positions fit your camera views and you actually measure them. Do not type it as fabricated ground truth.</li></ol>
<table border="1" cellpadding="5"><tr><th>Use</th><th>Example first-inner-corner (X,Y,Z) cm</th></tr><tr><td>fit 1–6</td><td>(-10,60,20), (-5,60,24), (-10,80,20), (-5,80,24), (-10,100,20), (-5,100,24)</td></tr><tr><td>validation 1–3</td><td>(-8,70,22), (-6,90,23), (-9,110,21)</td></tr></table>
<ol start="7"><li>Change Placement use to <b>validation</b> and capture three different measured placements. Click <b>Fit / validate installed pose</b>. Wait for <b>POSE PASSED</b>. If rejected, check origin, signs, first corner and measured level/parallel board position. Fix bad data rather than forcing Save.</li>
<li>Repeat on <b>2. Driver installed pose</b> in Fully Auto (the number may differ in fixed-source modes). Its board is on the driver side (negative Y), printed side toward the driver camera. Use the DRIVER corner/column convention in the picture. Do not simply copy the road XYZ list or reverse signs without measuring.</li>
<li>Road RIGHT needs no separate installed-pose tab. Its position/direction are derived from Road LEFT plus the saved stereo relationship. Finish <b>LCD physical mapping</b> next; poses passing alone do not save the whole rig.</li></ol>
""" + guide_image("rig_coordinates.png", "Panel origin and outward cameras with distinct road and driver board conventions") + "<p>This diagram is schematic, not to scale. Use your measured positions; do not copy distances from the drawing.</p>"

LCD_STEPS = """
<h2>3B. Register measured points on the actual LCD</h2>
<p><b>Before this tab:</b> the display and active dimensions must already be configured as described in Installed rig preparation. For Fully Auto, both installed camera-pose tabs must have passed. Stay inside the installed-rig window; do not close it to change parent settings after capturing unsaved poses. If the bound setup is wrong, close, correct it and restart the installed workflow.</p>
<p><b>LCD-only / Fully Manual route:</b> no camera-pose tabs are required. Before opening <b>3. Installed rig + LCD</b>, choose Stop, use Win+P &gt; Extend, enable Operation &gt; Operating Mode &gt; Show advanced configuration, select Research &gt; Prototype Display Output &gt; Target display and enable Use prototype display during Run. In Geometry &gt; Windshield, enter measured active Width/Height. Then open the installed-rig window, name the rig and tick <b>Camera order and mounts checked</b> after checking the current physical setup. LCD-only calibration does not create three camera positions.</p>
<ol><li>Select the <b>LCD physical mapping</b> tab (tab 3 in Fully Auto). Select Target 1 and <b>Show mark on selected LCD</b>. This covers the selected second monitor; the operator app remains on the laptop. If the dot is on the wrong display, stop and correct the target display before restarting this workflow.</li>
<li>Measure to the CENTRE of the dot from the same active-area bottom-centre origin. Enter <b>Measured X</b> and <b>Measured Z</b>, tick the confirmation, then <b>Capture measured mark</b>. Example: 8 cm left and 12 cm up gives X=-8, Z=12. Use your measured dot position, not a value computed by the app.</li>
<li>Repeat for all nine targets. Targets 1–6 build the mapping; 7–9 validate it. Use <b>Undo last mark</b> for a wrong entry, re-show the intended target and remeasure. Click <b>Fit / validate LCD mapping</b>; look for <b>LCD mapping PASSED</b>.</li>
<li>When every required camera tab and LCD mapping have passed, click <b>Save installed rig profile</b>. Read and dismiss the saved-success alert, then click <b>Close</b> in the installed-rig window. A pose-fit message alone is not a saved rig. The parent app reloads the saved result after that window closes.</li>
<li>Back in Cameras &gt; Calibration, tick <b>Confirm camera order and mounts</b> for this launch only after physically checking them. In Fully Auto, the scene should now show <b>Driver (index), Road L (index), Road R (index)</b> at their saved positions.</li></ol>
<p><b>If you do not see all three:</b> check Fully Auto mode, accepted saved driver/road profiles, accepted saved installed poses AND LCD mapping, unchanged indices/fingerprints/panel/display, and 3D settings &gt; <b>Camera positions</b>. Other operating modes may legitimately have fewer calibrated cameras. Rotate/zoom the scene if a marker is outside the view. Hover over rig status to inspect X/Y/Z. Do not enter made-up positions to force the picture.</p>
<p>The scene uses one centimetre coordinate system; perspective does not mean one real centimetre occupies one screen centimetre. The 8 cm arrows show orientation, not camera-case size or lens viewing angle. A plausible 3D view does not prove real dark-spot accuracy.</p>
<p><b>What success looks like:</b> the picture below uses a labelled, synthetic example rig to show the three camera markers. It is an illustration, not your saved calibration or a measured accuracy result. Your marker coordinates must come from your own accepted installed calibration.</p>
""" + guide_image("camera_rig_example.png", "Illustrative application view with Driver, Road L and Road R markers; synthetic values, no cameras connected")

VERIFY_STEPS = """
<h2>4. Final bench check, then reuse offline</h2>
<ol><li>Before Run, check saved indicators and physical camera identities/mounts. If using fixed driver distance, measure and hold that depth. If using ToF, require a commissioned controller, compatible profile and fresh valid readings.</li>
<li>Choose <b>Standby</b> first: each required feed must show the intended real camera. In this state no tracked blocking output is expected. Choose <b>Run</b> only when ready. With a valid compatible installed setup and selected secondary screen, Run opens output there. Standby or Stop releases that screen.</li>
<li>For independent alignment, use a stationary eye marker and a diffused test lamp. Stretch a thin line between lamp centre and eye marker; mark where it crosses the panel. Compare with the displayed spot centre. Record measured X/Z error in mm. Do not aim a high-intensity lamp directly into a person's eyes.</li>
<li>Repeat for both eye positions, several lamp positions/distances, and panel edges. Evaluate attenuation and latency separately using the project protocols. Do not call visual smoothness or a passed fitting threshold proof of physical accuracy.</li>
<li>After closing the app, back up the calibration folder and evidence. On the next offline launch, keep the same devices/ports/resolution/focus/mount/panel; check roles again, reuse matching profiles and confirm mounts. Recalibrate the affected stages after changes.</li></ol>
<h3>Quick recovery card</h3>
<table border="1" cellpadding="5"><tr><th>What you see</th><th>What to do</th></tr>
<tr><td>Setting/button is missing</td><td>Select the correct icon, expand its collapsed panel; check the selected operating mode. Scroll within the panel/guide.</td></tr>
<tr><td>No accepted board capture</td><td>Check whole pattern, white border, lighting, sharpness, correct camera and square count; count only accepted captures.</td></tr>
<tr><td>Fit passed but no saved status</td><td>Click the separate Save button and wait for confirmation. Stop if saving fails; inspect the displayed path/write access.</td></tr>
<tr><td>ToF waits forever</td><td>Check the hardware/bridge gate. No commissioned controller: Skip ToF and use a measured fixed distance.</td></tr>
<tr><td>Only one/zero calibrated camera markers</td><td>Follow the three-camera checklist in LCD mapping; component calibration alone is insufficient.</td></tr>
<tr><td>No dot on second display</td><td>Check Extend, target display, Use prototype display during Run ON, session mode, compatible installed setup and fresh observations. Do not disable quality gates.</td></tr>
<tr><td>Spots move to the wrong side</td><td>Stop. Check the physical first corner, camera order and global X/Y/Z signs. Never compensate by swapping random settings.</td></tr>
<tr><td>Guide/video link fails offline</td><td>Use local written steps/pictures. Videos require internet and are optional. Missing local pictures means the app copy is incomplete.</td></tr></table>
<p><b>Calibrate Center</b> is a demo preview recentering action, not a replacement for lens or installed-rig calibration. It is disabled for installed coordinates and should not be used to repair wrong physical alignment.</p>
"""

ALL_GUIDE_SECTIONS = [("Offline preparation", OFFLINE_STEPS), ("Road cameras", ROAD_STEPS),
                      ("Driver camera", DRIVER_STEPS), ("ToF sensor", TOF_STEPS),
                      ("Installed rig", RIG_STEPS), ("LCD mapping", LCD_STEPS), ("Verify", VERIFY_STEPS)]


def overview_sections(mode: OperatingMode, stereo: bool):
    policy = policy_for(mode)
    topics = []
    if policy.use_road_camera and stereo:
        topics.append(("Road cameras", ROAD_STEPS))
    if policy.use_driver_camera:
        topics.extend((("Driver camera", DRIVER_STEPS), ("ToF sensor", TOF_STEPS)))
    if policy.use_driver_camera or policy.use_road_camera:
        topics.append(("Installed rig", RIG_STEPS))
    start = f'''<h2>Start here — {escape(mode.value)}</h2>
    <p><b>To calibrate and display all THREE cameras, choose Fully Auto before starting the complete workflow.</b> Fixed-source modes calibrate fewer camera roles.</p>
    <p>All settings start collapsed. Choose the Operation icon, expand Operating Mode and select your mode.
    Choose the Camera icon, expand Calibration and click <b>Calibration guide...</b> to return here.</p>
    <p>Use the tabs in order. The <b>ToF sensor</b> tab is optional and separate from camera calibration.
    Fit means calculate; validation means check with new measurements; Save means keep the accepted result for later.</p>
    <p><b>Selected mode: {escape(mode.value)}</b>.</p>'''
    if policy.use_road_camera and not stereo:
        start += '<p>A single road camera is a development preview; the installed road workflow requires a calibrated stereo pair.</p>'
    if not policy.use_driver_camera and not policy.use_road_camera:
        start += '<p>Fully Manual uses measured eye/lamp coordinates typed by you. It can calibrate LCD mapping, but does not create three calibrated camera poses.</p>'
    start += OFFLINE_STEPS
    return [("Start here", start), *topics, ("LCD mapping", LCD_STEPS), ("Verify", VERIFY_STEPS)]
