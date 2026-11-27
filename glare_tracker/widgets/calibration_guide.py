"""Plain-English help shared by the calibration entry point and dialogs."""

from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLayout, QTabWidget, QTextBrowser, QVBoxLayout

from glare_tracker.operating_modes import OperatingMode, policy_for
from glare_tracker.widgets.icons import command_button


def size_calibration_dialog(dialog: QDialog, width: int, height: int) -> None:
    screen = dialog.screen()
    if screen is not None:
        area = screen.availableGeometry()
        width = min(width, area.width() - 32)
        height = min(height, area.height() - 48)
    dialog.resize(width, height)


class CalibrationActions(QLayout):
    """Keep the same command order when a row wraps on a small screen."""

    def __init__(self, *buttons, stretch=True):
        super().__init__()
        self._items = []
        self._stretch = stretch
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)
        for button in buttons:
            self.addWidget(button)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < self.count() else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < self.count() else None

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def sizeHint(self):
        widths = sum(item.sizeHint().width() for item in self._items)
        return QSize(widths + self.spacing() * max(0, self.count() - 1),
                     self.minimumSize().height())

    def expandingDirections(self):
        return Qt.Horizontal

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def _arrange(self, rect, place):
        spacing = self.spacing()
        rows = []
        row = []
        used = 0
        for item in self._items:
            width = item.sizeHint().width()
            if row and used + spacing + width > rect.width():
                rows.append((row, used))
                row, used = [], 0
            used += width + (spacing if row else 0)
            row.append(item)
        if row:
            rows.append((row, used))

        y = rect.y()
        for row, used in rows:
            height = max(item.sizeHint().height() for item in row)
            if place:
                x = rect.x()
                spread = self._stretch and (len(row) > 1 or len(rows) == 1)
                extra = max(0, rect.width() - used) // len(row) if spread else 0
                for item in row:
                    width = item.sizeHint().width() + extra
                    item.setGeometry(QRect(x, y, width, height))
                    x += width + spacing
            y += height + spacing
        return max(0, y - rect.y() - spacing)


class CalibrationGuideDialog(QDialog):
    def __init__(self, title, sections, parent=None, *, current=0):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        for label, html in sections:
            browser = QTextBrowser()
            browser.setObjectName("calibrationGuideText")
            browser.setAccessibleName(f"{label} instructions")
            browser.setOpenExternalLinks(True)
            document = browser.document()
            document.setDocumentMargin(18)
            document.setDefaultStyleSheet(
                "body { color: #d9dde3; font-family: 'Segoe UI'; font-size: 12px; } "
                "h2 { font-size: 18px; } h3 { font-size: 14px; color: #b6d6ff; } "
                "p, li { margin-bottom: 7px; } a { color: #9bc9ff; } "
                "pre { font-family: Consolas, monospace; color: #d0e4fd; }"
            )
            browser.setHtml(html)
            self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(current)
        layout.addWidget(self.tabs, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        close = command_button("Return to calibration", "back")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        size_calibration_dialog(self, 820, 680)


ROAD_STEPS = """
<h2>Set up the two road cameras</h2>
<p>Stereo means using two cameras to work out how far away the light is.
Start with the dark filters removed. Use the same camera resolution for both feeds.</p>
<ol>
  <li>Select <b>Stop</b>. In <b>Cameras &gt; Camera Selection</b>, assign the two
  physical cameras to <b>Road LEFT camera</b> and <b>Road RIGHT camera</b>.</li>
  <li>Open <b>1. Calibrate road stereo...</b>. Use <b>Print A4 chessboard...</b>.
  Print at <b>Actual size (100%)</b> and glue the sheet to a stiff, flat board.
  Count the inner intersections (9 across and 6 down). Measure several squares
  and enter the average side length in centimetres. A 20 mm square is 2.0 cm.</li>
  <li>Select <b>Start LEFT calibration</b>. Take at least 15 sharp pictures with
  <b>Capture LEFT view</b>. Move the board across the image, bring it near and far,
  and tilt it a little. Keep the full board in view. Select <b>Fit LEFT intrinsics</b>
  to calculate that camera's settings. Repeat for RIGHT when the app advances.</li>
  <li>Measure the distance between the centres of the two lenses. Select
  <b>Start STEREO calibration</b>. Put the board on a stand where both cameras
  can see it. After each move, let it settle and select <b>Capture pair</b>.
  Take at least 15 pairs at different positions.</li>
  <li>Select <b>Fit stereo geometry</b>. Check that the reported lens separation
  (the baseline) agrees with your measurement. Select <b>Save stereo profile</b>
  and wait for the saved confirmation.</li>
</ol>
<h3>If the fit fails</h3>
<p>Check for curled paper, blurred pictures, repeated positions, or a swapped
camera. Compare resolution labels in the paired stage. Different lenses can make
the board look slightly larger in one feed.</p>
<p>Mount the final filters without shifting the cameras. Check known target
positions and distances with the filters installed before collecting results.</p>
<p><a href="https://www.youtube.com/watch?v=kizO_s-YUDU">Watch a paired checkerboard capture on YouTube</a></p>
"""


DRIVER_STEPS = """
<h2>Set up the driver camera</h2>
<p>This step teaches the app how the driver camera sees. The installed rig step
will teach it where the camera is mounted.</p>
<ol>
  <li>In <b>Cameras &gt; Camera Selection</b>, check the <b>Driver camera</b>.
  Open <b>2. Calibrate driver camera / ToF...</b> and select <b>1. Driver camera</b>.</li>
  <li>Use <b>Print A4 chessboard...</b> if you need a board. Print at 100% and
  glue the sheet to a flat backing. Enter the measured square size in
  centimetres. Keep the camera focus fixed.</li>
  <li>Select <b>Start camera</b>. Select <b>Capture view</b> at least 15 times.
  Move the board to the centre, sides and corners of the image. Change the
  distance and tilt slightly between pictures. Pause for a sharp image.</li>
  <li>Select <b>Fit camera</b>. If it passes, select <b>Save camera profile</b>
  and wait for the confirmation. If the fit fails, check the square size,
  the flatness of the board and the variety of the pictures.</li>
</ol>
<h3>If you only have the camera</h3>
<p>Open <b>2. ToF sensor</b> and select <b>Skip ToF for now</b>. In
<b>Driver &gt; Driver Distance</b>, leave <b>Live driver distance</b> off.
Measure straight forward from the camera to the level of your eyes and enter it
as <b>Fixed distance</b>. For example, enter 52 cm if you measure 52 cm. Sit at
that distance during the bench test. The camera still tracks your eyes.</p>
<p><a href="https://www.youtube.com/watch?v=H5qbRTikxI4&amp;t=230s">Watch why you move the checkerboard on YouTube</a></p>
"""


TOF_STEPS = """
<h2>Set up the optional distance sensor</h2>
<p>ToF means time of flight. The sensor measures distance to a surface. You
need the VL53L0X, a controller running the GlareTracker bridge v1, and a USB cable.
Without the controller, select <b>Skip ToF for now</b>.</p>
<ol>
  <li>Fix the sensor close to the driver camera, pointing in the same direction.
  Select its USB serial (COM) port and choose <b>Connect / reconnect</b>.
  Wait for valid readings.</li>
  <li>Set a flat target in front of the sensor. Measure from the sensor's
  reference surface. Enter the measured distance, set <b>Sample use</b>
  to <b>fit</b>, and select <b>Capture 20 readings</b>. Repeat at three
  different distances. For example, try 30, 50 and 70 cm.</li>
  <li>Set <b>Sample use</b> to <b>validation</b> and repeat at two new distances,
  such as 40 and 60 cm. The app uses these to check its distance correction.</li>
  <li>Enter the two signed offsets you measured from the installed setup.
  One is the sensor's position along the camera's forward axis. The other
  shifts the measured face surface to the eye plane along that axis.
  Confirm both measurements and select <b>Fit and Save ToF</b>. Enter zero
  only when your measurement is zero.</li>
</ol>
<p>Compare the resulting live eye distance with an independent measurement
before using it in a trial. A hand, glasses or the background can affect a
sensor reading. With the sensor skipped, <b>Live driver distance</b> off uses
your fixed distance. Turning it on uses a camera estimate based on the distance
between the pupils.</p>
"""


RIG_STEPS = """
<h2>Measure where the cameras are mounted</h2>
<p>Save the relevant camera profiles first. Fix the LCD, cameras and final
filters in place. Keep the road cameras aimed toward the road and the driver
camera aimed toward the driver. Put the board on the side the camera can see.</p>
<h3>Use the bottom centre of the screen as zero</h3>
<p>Mark the middle of the bottom edge of the <b>active image area</b>. Use
that point for every measurement. Stand on the driver side when deciding
what counts as left and right.</p>
<pre>Driver side (-Y)     | LCD (Y = 0) |     Road side (+Y)
Board &lt;-- Driver cam |             | Road cams --&gt; Board</pre>
<ul>
  <li><b>X:</b> sideways. Right is positive and left is negative.</li>
  <li><b>Y:</b> distance straight out from the screen plane. Road is positive
  and driver is negative.</li>
  <li><b>Z:</b> height above the bottom edge. Up is positive.</li>
</ul>
<p><b>Example:</b> A board corner 10 cm left of centre, 80 cm toward the road
and 20 cm above the bottom edge is <b>X = -10, Y = 80, Z = 20</b>.
A point the same distance toward the driver has <b>Y = -80</b>.</p>
<h3>Capture each camera tab shown in the dialog</h3>
<ol>
  <li>Open <b>3. Calibrate installed rig / LCD...</b>. Give the mount a name,
  such as <b>rig-v1</b>, and confirm the physical camera positions.</li>
  <li>Put the board on a stand, parallel to the LCD. Mark its first inner
  corner. For Road LEFT this is the upper-left inner corner as seen from
  the driver side. For the driver camera it is the upper-left inner corner
  as seen from the road side. Check that the board faces its camera.
  The three rotation fields are zero when the board is parallel and level.
  For a tilted board, measure the right-hand angles around LCD X, Y and Z
  with an angle gauge. The app applies them in that order.</li>
  <li>Select <b>Start preview</b>. Enter the square size and the measured
  <b>First inner corner</b> X, Y and Z. Under <b>Placement use</b> choose
  <b>fit</b>, tick the confirmation and select <b>Capture measured placement</b>.</li>
  <li>On the frozen picture, check that corner <b>1</b> matches your mark.
  If it is wrong, select <b>Undo last placement</b> and try again with
  <b>Reverse detected corner order</b> if the board is numbered from the opposite end.
  Select <b>Resume preview</b> before the next capture.</li>
  <li>Capture <b>six fit placements</b> at <b>three or more Y depths</b>. Move
  the board up, down or sideways between placements too. Then switch to
  <b>validation</b> and capture <b>three new placements</b>. Select
  <b>Fit / validate installed pose</b> and look for <b>POSE PASSED</b>.</li>
</ol>
<p>Repeat for the driver tab if it is present. Road RIGHT uses the relationship
saved in the stereo profile. If a fit fails, check signs, corner order and
the board position before repeating. If you move a mount or change the
camera focus or resolution later, check the calibration again.</p>
<p><a href="https://www.youtube.com/watch?v=ND2fa08vxkY">Watch how a camera position and direction are described on YouTube</a></p>
"""


LCD_STEPS = """
<h2>Match physical positions to dots on the LCD</h2>
<p>This step teaches the app which screen pixel belongs to a measured point
on the panel. It works even when the cameras face away from the LCD.</p>
<ol>
  <li>Connect the final LCD. In Windows, press <b>Win + P</b> and select
  <b>Extend</b>. In GlareTracker, enable <b>Show advanced configuration</b>
  under <b>Operation</b>. Under <b>Research &gt; Prototype Display Output</b>,
  select the LCD as <b>Target display</b>.</li>
  <li>Check the active image width and height in <b>Geometry &gt; Windshield</b>.
  Measure the lit image area inside the frame.</li>
  <li>Open <b>3. Calibrate installed rig / LCD...</b> and select
  <b>LCD physical mapping</b>. Choose the next <b>Target</b> and select
  <b>Show mark on selected LCD</b>.</li>
  <li>Measure to the centre of the dot from the same bottom-centre point.
  Enter <b>Measured X</b> (sideways) and <b>Measured Z</b> (up).
  For example, a dot 8 cm left and 12 cm up is <b>X = -8, Z = 12</b>.
  Tick the measurement confirmation and select <b>Capture measured mark</b>.</li>
  <li>Repeat for targets 1 to 9. The first six build the mapping and the last
  three check it. If you entered a wrong measurement, use <b>Undo last mark</b>
  and measure it again. Select <b>Fit / validate LCD mapping</b> and look for
  <b>LCD mapping PASSED</b>.</li>
  <li>After the required camera tabs and LCD mapping pass, select
  <b>Save installed rig profile</b>. Return to <b>Cameras &gt; Calibration</b>
  and select <b>Confirm camera order and mounts</b> before <b>Run</b>.</li>
</ol>
<p>If no dot appears, check that Windows is in Extend mode and that the
selected display is the secondary LCD. If the mapping fails, recheck the
panel dimensions and each measured dot, including the sign of X.</p>
"""


VERIFY_STEPS = """
<h2>Check the real blocking spot</h2>
<ol>
  <li>On the bench, put a marker at the eye position and use a diffused lamp.
  Stretch a thin line from the lamp centre to the eye marker.</li>
  <li>Mark where the line crosses the screen. Compare that point with the
  centre of the spot GlareTracker displays. Record the gap in millimetres.</li>
  <li>Repeat for the two eye positions, several lamp distances, and the centre
  and edges of the panel. Measure glare reduction and response time separately.</li>
</ol>
<p>In fixed-position modes, enter measured eye or lamp coordinates under
<b>Driver</b> or <b>Road lights</b>. Use the same LCD origin. The
<b>Calibrate Center</b> toolbar button adjusts the preview centre.</p>
"""


def overview_sections(mode: OperatingMode, stereo: bool) -> list[tuple[str, str]]:
    policy = policy_for(mode)
    steps = []
    topics = []
    if policy.use_road_camera and stereo:
        steps.append("Calibrate road stereo. Set up the two cameras that see the lamp.")
        topics.append(("Road cameras", ROAD_STEPS))
    elif policy.use_road_camera:
        steps.append("Use Calibrate single-camera distances for a one-camera preview. "
                     "Use a calibrated stereo pair for installed road-camera measurement.")
    if policy.use_driver_camera:
        steps.append("Calibrate the driver camera. Set up or skip the optional distance sensor.")
        topics.append(("Driver camera", DRIVER_STEPS))
    if policy.use_road_camera or policy.use_driver_camera:
        steps.append("Calibrate the installed rig and LCD. Measure the physical positions and save.")
        topics.append(("Installed rig", RIG_STEPS))
    else:
        steps.append("Calibrate the LCD. Measure the displayed dots and save.")
    items = "".join(f"<li>{step}</li>" for step in steps)
    start = f"""
    <h2>Start here</h2>
    <p><b>Selected mode: {mode.value}</b>. Follow the steps for the cameras you
    use. You can change the mode under <b>Operation</b>.</p>
    <ol>{items}</ol>
    <h3>Before you start</h3>
    <p>Work on a stationary bench. Have a centimetre ruler or tape measure,
    a flat A4 checkerboard on stiff backing, a stand to hold it, and the final
    LCD. Choose <b>Stop</b>, wait for camera discovery to finish, and close
    other apps using the cameras.</p>
    <h3>What the buttons mean</h3>
    <p><b>Capture</b> keeps one view or measurement. <b>Fit</b> calculates the
    settings from your fit samples. <b>Validation</b> checks the settings using
    different samples. <b>Save</b> keeps a profile for later use. Look for the
    saved confirmation before moving on.</p>
    <p>Open the tabs above for each stage. Inside a calibration window,
    select its guide button to revisit the steps.</p>
    """
    if not policy.use_driver_camera and not policy.use_road_camera:
        start += ("<p>In <b>Fully Manual</b>, enter the eye and lamp positions by hand. "
                  "Use <b>LCD mapping</b> for output on a physical screen.</p>")
    return [("Start here", start), *topics, ("LCD mapping", LCD_STEPS), ("Verify", VERIFY_STEPS)]
