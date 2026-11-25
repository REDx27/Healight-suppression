"""Driver camera and ToF calibration with independent development skips."""

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget, QScrollArea, QFrame,
)

from glare_tracker.calibration import _calibration_dir
from glare_tracker.installation import camera_model, camera_record, fit_tof, validate_tof_profile
from glare_tracker.tof import ToFSerialWorker
from glare_tracker.widgets.stereo_calibration import (
    MIN_SAMPLES, SingleBoardCapture, SingleBoardFit,
    calibration_guide_asset_path, printable_chessboard_path,
)


def number(value=0., minimum=-1000., maximum=1000., suffix=" cm"):
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(3)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin


def note(text):
    label = QLabel(text)
    label.setWordWrap(True)
    return label


def scroll_page(page):
    scroll = QScrollArea()
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setWidget(page)
    return scroll


def safe_load(store, name):
    try:
        return store.load(name)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def session_folder(prefix):
    path = _calibration_dir() / "installation_sessions" / (
        prefix + datetime.now(timezone.utc).strftime("_%Y%m%dT%H%M%S_%fZ"))
    path.mkdir(parents=True, exist_ok=False)
    return path


CAMERA_GUIDE = """
<h1>1. Driver camera</h1>
<h2>1.1 Prepare the camera and flat target</h2>
<p>Select the actual driver webcam. Set its final focus and image mode; do not move
or refocus it after installed-rig calibration. Print the supplied 9 x 6 INNER-corner
board (10 x 7 squares) at 100%, not Fit to page. Measure several squares: the supplied
pattern is 20 mm. Glue it to a completely rigid flat backing.</p>
<h2>1.2 Collect varied views</h2>
<p>Open Camera, choose Start camera and hold the whole board visible. Capture at least
15 sharp views. Cover the centre, all edges and corners, near/far distances and gentle
horizontal/vertical tilts. Move the BOARD between views. Blur, a curved board and
15 nearly identical pictures can produce a bad lens model.</p>
<h2>1.3 Fit, inspect, save</h2>
<p>Fit driver intrinsics, inspect RMS and image size, then explicitly Save camera
profile. A successful fit is not saved until this action. Save shows a success alert.
The preview and fit use native unmirrored pixels; the later face preview may be mirrored.</p>
<h2>1.4 What this stage establishes</h2>
<p>This stage calibrates focal length, principal point and lens distortion. It does
not locate the camera relative to the LCD or establish true eye depth. After mounting
the final rig, complete Installed Rig Calibration. Skip camera is for development
previews only and never changes the status to Calibrated.</p>
<p>For a stable no-ToF bench preview, use Driver &gt; Driver Distance and keep Live driver
distance OFF. Enter the measured fixed optical-axis distance to the eye plane. Eye
tracking stays live. ON restores IPD or selected ToF distance estimation.</p>
"""

TOF_GUIDE = """
<h1>2. ToF sensor</h1>
<h2>2.1 Connect and identify the sensor</h2>
<p>Connect VL53L0X to a suitable microcontroller over I2C and the controller to the PC
over USB. Use the documented GlareTracker bridge v1 firmware/protocol. An ordinary
Arduino distance-printing sketch does not provide the required status and timestamps.
Choose the COM port and Connect. Until real, synchronized valid samples arrive, the
sensor remains Not connected / Not calibrated. No hardware? Use Skip ToF.</p>
<h2>2.2 Fix the sensor mount</h2>
<p>Fix it close to the camera, with parallel axes toward the forehead/upper face.
Measure sensor Z offset along the driver camera's forward axis. Do not aim through
the LCD, obstruct the optics or assume a face return is the pupil position. This first
model is limited to near-frontal poses (within 10 degrees) with the eye midpoint
within 5 degrees of the camera axis. Validate this small working region physically.</p>
<h2>2.3 Range bias and held-out checks</h2>
<p>Use a stable flat target filling the sensing area. Measure distance from the sensor
reference. At each position wait for at least 20 stable valid readings, enter the
measured distance, select Fit or Validation and Capture distance. Use three distinct
fit distances, then two different held-out distances spanning the seating region.
Invalid returns are excluded. Fit uses only fit samples; validation is never fitted.</p>
<h2>2.4 Eye-depth correction</h2>
<p>Measure the facial-surface-to-eye-plane Z correction with a safe rigid reference
or independently measured eye target; enter a signed offset. Enter the measured
sensor-to-camera Z offset separately. Confirm both measurements. A zero is acceptable
only when measured. The sensor is a single-zone range device and can see a hand,
glasses or background instead of the intended surface.</p>
<h2>2.5 Save and verify</h2>
<p>Fit and Save ToF profile only after held-out range limits pass. This is a sensor
bias/mount profile, not a claim that face/eye accuracy is validated. Verify real faces,
different depths, pose, glasses and incoming glare independently. Missing eyes, stale
range or invalid quality must clear ToF-based physical output. Skipping ToF selects
camera-only IPD when Live driver distance is ON, or the fixed reference when OFF;
neither is a calibrated ToF result.</p>
"""


class DriverCalibrationGuide(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Driver calibration guide - camera, then ToF")
        self.resize(850, 700)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        for title, html in (("1. Camera", CAMERA_GUIDE), ("2. ToF sensor", TOF_GUIDE)):
            browser = QTextBrowser()
            browser.setHtml(html)
            if title.startswith("1"):
                for asset in ("flat_board.svg", "pose_coverage.svg"):
                    browser.append(f'<p><img width="680" src="{calibration_guide_asset_path(asset).as_uri()}"></p>')
            tabs.addTab(browser, title)
        layout.addWidget(tabs)
        close = QPushButton("Return to calibration")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class DriverCalibrationDialog(QDialog):
    def __init__(self, camera_index, store, skips=None, parent=None):
        super().__init__(parent)
        self.index, self.store = camera_index, store
        self.skips = dict(skips or {"camera": False, "tof": False})
        self.capture_worker = self.fit_worker = self.sensor_worker = None
        self._accept_camera_samples = False
        self.candidate = None
        self.frames, self.corners, self.range_samples = [], [], []
        self.recent = deque(maxlen=100)
        self.saved_camera = safe_load(store, f"driver_{camera_index}")
        if self.saved_camera:
            try:
                camera_model(self.saved_camera)
            except (ValueError, TypeError, KeyError):
                self.saved_camera = None
        self.saved_tof = safe_load(store, "tof")
        if self.saved_tof:
            try:
                validate_tof_profile(self.saved_tof)
            except (ValueError, KeyError, TypeError):
                self.saved_tof = None
        self.session_dir = None
        self.setWindowTitle("Driver side - camera and ToF calibration")
        self.resize(880, 750)
        layout = QVBoxLayout(self)
        self.camera_indicator = note("")
        self.tof_indicator = note("")
        layout.addWidget(self.camera_indicator)
        layout.addWidget(self.tof_indicator)
        layout.addWidget(note("Calibrate the camera first, then the sensor. Each can be skipped separately for development. Installed rig alignment is a third, separate calibration."))
        self.tabs = QTabWidget()
        self.tabs.addTab(scroll_page(self._camera_page()), "1. Driver camera")
        self.tabs.addTab(scroll_page(self._tof_page()), "2. ToF sensor")
        layout.addWidget(self.tabs, 1)
        actions = QHBoxLayout()
        self.guide = QPushButton("Camera and ToF guide...")
        self.print_board = QPushButton("Print A4 chessboard...")
        close = QPushButton("Close")
        for button in (self.guide, self.print_board, close):
            actions.addWidget(button)
        self.guide.clicked.connect(lambda: DriverCalibrationGuide(self).exec_())
        self.print_board.clicked.connect(self._print)
        close.clicked.connect(self.reject)
        layout.addLayout(actions)
        self._refresh_indicators()

    def _refresh_indicators(self):
        self.camera_indicator.setText("CAMERA: " + ("SKIPPED for this session" if self.skips["camera"] else
            "Calibrated (lens fit saved; installed pose is separate)" if self.saved_camera else "Not calibrated"))
        self.tof_indicator.setText("ToF: " + ("SKIPPED - fixed/IPD depth is chosen in Driver settings" if self.skips["tof"] else
            "Calibrated range profile saved; live connection still required" if self.saved_tof else "Not calibrated / not connected"))

    def _camera_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(note(f"Driver camera {self.index}. Native 640 x 480 capture. Supplied board: 9 x 6 inner corners. Measure the square before capture."))
        self.square = number(2., .1, 20.)
        form = QFormLayout()
        form.addRow("Measured square side:", self.square)
        self.ipd = number(6.3, 3., 9.)
        form.addRow("Measured eye separation (IPD):", self.ipd)
        layout.addLayout(form)
        self.preview = QLabel("Camera preview starts only when requested")
        self.preview.setMinimumSize(420, 240)
        self.preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview, 1)
        self.camera_message = note(f"0 / {MIN_SAMPLES} varied views. Start the camera with a rigid flat board.")
        layout.addWidget(self.camera_message)
        row = QHBoxLayout()
        self.start = QPushButton("Start camera")
        self.take = QPushButton("Capture view")
        self.fit = QPushButton("Fit camera")
        self.save_camera = QPushButton("Save camera profile")
        self.skip_camera = QPushButton("Skip camera for now")
        for button in (self.start, self.take, self.fit, self.save_camera, self.skip_camera):
            row.addWidget(button)
        self.take.setEnabled(False)
        self.fit.setEnabled(False)
        self.save_camera.setEnabled(False)
        self.start.clicked.connect(self._start_camera)
        self.take.clicked.connect(lambda: self.capture_worker.capture_requested.set())
        self.fit.clicked.connect(self._fit_camera)
        self.save_camera.clicked.connect(self._save_camera)
        self.skip_camera.clicked.connect(lambda: self._skip("camera"))
        layout.addLayout(row)
        recovery = QHBoxLayout()
        self.reset_camera = QPushButton("Reset captured camera views")
        self.use_saved_camera = QPushButton("Use saved camera profile")
        self.use_saved_camera.setEnabled(self.saved_camera is not None)
        self.reset_camera.clicked.connect(self._reset_camera_views)
        self.use_saved_camera.clicked.connect(lambda: self._use_saved("camera"))
        recovery.addWidget(self.reset_camera)
        recovery.addWidget(self.use_saved_camera)
        layout.addLayout(recovery)
        return page

    def _tof_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(note("No controller connected yet? Skip ToF and calibrate the camera independently. A saved range profile never replaces a live, valid sensor reading."))
        form = QFormLayout()
        self.port = QComboBox()
        self.port.setEditable(True)
        try:
            from serial.tools.list_ports import comports
            self.port.addItems([port.device for port in comports()])
        except ImportError:
            pass
        if self.saved_tof:
            self.port.setEditText(self.saved_tof.get("port", ""))
        form.addRow("USB serial port:", self.port)
        self.reference = number(50., 5., 150.)
        form.addRow("Measured target distance:", self.reference)
        self.split = QComboBox()
        self.split.addItems(["fit", "validation"])
        form.addRow("Sample use:", self.split)
        self.sensor_z = number()
        self.eye_offset = number()
        form.addRow("Sensor-to-camera Z offset:", self.sensor_z)
        form.addRow("Surface-to-eye Z correction:", self.eye_offset)
        self.offsets_confirmed = QCheckBox("I independently measured both signed offsets")
        form.addRow(self.offsets_confirmed)
        layout.addLayout(form)
        self.sensor_message = note("NOT CONNECTED. No synthetic readings are used by this dialog.")
        self.range_message = note("No range samples captured")
        layout.addWidget(self.sensor_message)
        layout.addWidget(self.range_message)
        row = QHBoxLayout()
        self.connect_sensor = QPushButton("Connect / reconnect")
        self.capture_range = QPushButton("Capture 20 readings")
        self.save_tof = QPushButton("Fit and Save ToF")
        self.skip_tof = QPushButton("Skip ToF for now")
        for button in (self.connect_sensor, self.capture_range, self.save_tof, self.skip_tof):
            row.addWidget(button)
        self.connect_sensor.clicked.connect(self._connect_sensor)
        self.capture_range.clicked.connect(self._capture_range)
        self.save_tof.clicked.connect(self._save_tof)
        self.skip_tof.clicked.connect(lambda: self._skip("tof"))
        layout.addLayout(row)
        recovery = QHBoxLayout()
        self.reset_ranges = QPushButton("Reset captured ToF distances")
        self.use_saved_tof = QPushButton("Use saved ToF profile")
        self.use_saved_tof.setEnabled(self.saved_tof is not None)
        self.reset_ranges.clicked.connect(self._reset_range_samples)
        self.use_saved_tof.clicked.connect(lambda: self._use_saved("tof"))
        recovery.addWidget(self.reset_ranges)
        recovery.addWidget(self.use_saved_tof)
        layout.addLayout(recovery)
        layout.addStretch()
        return page

    def _print(self):
        if not printable_chessboard_path().is_file() or not QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(printable_chessboard_path()))):
            self.camera_message.setText("Could not open the printable board. See the guide for exact target dimensions.")

    def _stop_camera(self):
        self._accept_camera_samples = False
        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.requestInterruption()
            if not self.capture_worker.wait(5000):
                self.camera_message.setText("Waiting for camera release; try again shortly.")
                return False
        self.take.setEnabled(False)
        return True

    def _start_camera(self):
        if self.fit_worker and self.fit_worker.isRunning():
            return
        if not self._stop_camera():
            return
        if self.session_dir is None:
            try:
                self.session_dir = session_folder("driver")
            except OSError as error:
                self.camera_message.setText(str(error))
                return
        self.square.setEnabled(False)
        self.capture_worker = SingleBoardCapture(self.index, (9, 6), "driver", self)
        worker = self.capture_worker
        self.capture_worker.preview.connect(lambda image: self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(700, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        self.capture_worker.status.connect(self.camera_message.setText)
        self.capture_worker.sample.connect(lambda payload: self._camera_sample(payload)
                                           if worker is self.capture_worker else None)
        self.capture_worker.finished.connect(lambda: self.take.setEnabled(False)
                                             if worker is self.capture_worker else None)
        self._accept_camera_samples = True
        self.capture_worker.start()
        self.take.setEnabled(True)

    def _camera_sample(self, payload):
        if not self._accept_camera_samples:
            return
        frame, corners = payload
        if any(np.sqrt(np.mean((corners - previous) ** 2)) < 8 for previous in self.corners):
            self.camera_message.setText("Similar pose: move/tilt the board and capture again.")
            return
        if not cv2.imwrite(str(self.session_dir / f"driver_{len(self.frames):03}.png"), frame):
            self.camera_message.setText("Could not archive the frame; it was not accepted.")
            return
        self.frames.append(frame)
        self.corners.append(corners.copy())
        self.camera_message.setText(f"{len(self.frames)} / {MIN_SAMPLES} minimum views. Cover centre, edges, near/far and tilts.")
        self.fit.setEnabled(len(self.frames) >= MIN_SAMPLES)
        self.candidate = None
        self.save_camera.setEnabled(False)

    def _fit_camera(self):
        if not self._stop_camera() or (self.fit_worker and self.fit_worker.isRunning()):
            return
        self.fit.setEnabled(False)
        self.candidate = None
        self.save_camera.setEnabled(False)
        self.start.setEnabled(False)
        self.reset_camera.setEnabled(False)
        self.fit_worker = SingleBoardFit(self.frames, (9, 6), self.square.value(), self)
        self.fit_worker.result_ready.connect(self._camera_fitted)
        self.fit_worker.failed.connect(self.camera_message.setText)
        self.fit_worker.finished.connect(lambda: (self.start.setEnabled(True), self.fit.setEnabled(True), self.reset_camera.setEnabled(True)))
        self.fit_worker.start()

    def _camera_fitted(self, result):
        self.candidate = result
        self.camera_message.setText(f"FIT PASSED: RMS {result.rms_error:.3f} px, {result.image_size}. Click Save camera profile to activate.")
        self.save_camera.setEnabled(True)

    def _save_camera(self):
        if self.candidate is None:
            return
        try:
            record = camera_record(self.candidate, self.index)
            record["ipd_cm"] = self.ipd.value()
            record["sample_count"] = len(self.frames)
            record["square_size_cm"] = self.square.value()
            record["evidence"] = str(self.session_dir)
            path = self.store.save(f"driver_{self.index}", record)
        except (ValueError, OSError) as error:
            self.camera_message.setText(str(error))
            return
        self.saved_camera = record
        self.use_saved_camera.setEnabled(True)
        self.skips["camera"] = False
        self._refresh_indicators()
        self.camera_message.setText(f"Camera lens calibration saved: {path.name}. Continue with ToF or skip it separately.")
        QMessageBox.information(self, "Driver camera calibrated", "Driver lens profile saved successfully. Installed-rig calibration is still required for LCD alignment.")

    def _connect_sensor(self):
        if self.sensor_worker and not self.sensor_worker.stop():
            return
        self.recent.clear()
        self.sensor_worker = ToFSerialWorker(self.port.currentText().strip(), self)
        worker = self.sensor_worker
        self.sensor_worker.status.connect(self.sensor_message.setText)
        self.sensor_worker.sample.connect(lambda sample: self._range_sample(sample)
                                          if worker is self.sensor_worker else None)
        self.sensor_worker.start()

    def _range_sample(self, sample):
        if sample["valid"]:
            self.recent.append(sample)
            self.sensor_message.setText(f"Valid range: {sample['raw_cm']:.2f} cm | {sample['device_id']}")
        else:
            self.recent.clear()

    def _capture_range(self):
        now = time.monotonic_ns()
        recent = [s for s in self.recent if 0 <= now - s["observed_ns"] <= 2_000_000_000]
        if len(recent) < 20:
            self.range_message.setText("Wait for at least 20 fresh valid readings from a stationary target.")
            return
        if any(s["reference_cm"] == self.reference.value() for s in self.range_samples):
            self.range_message.setText("This reference distance is already captured; use a different held-out distance.")
            return
        values = [s["raw_cm"] for s in recent[-20:]]
        self.range_samples.append({"reference_cm": self.reference.value(), "raw_cm": values,
                                   "split": self.split.currentText(), "device_id": recent[-1]["device_id"]})
        self.recent.clear()
        self.range_message.setText(f"{len(self.range_samples)} distances captured; fit needs 3 fit and 2 separate validation distances.")

    def _save_tof(self):
        try:
            if not self.offsets_confirmed.isChecked():
                raise ValueError("Independently measure and confirm the sensor and eye-plane offsets")
            devices = {s["device_id"] for s in self.range_samples}
            if len(devices) != 1:
                raise ValueError("Collect samples from exactly one identified sensor")
            record = fit_tof(self.range_samples, devices.pop(), self.sensor_z.value(), self.eye_offset.value())
            record["port"] = self.port.currentText().strip()
            record["measurements"] = self.range_samples
            self.store.save("tof", record)
        except (ValueError, OSError) as error:
            self.range_message.setText(str(error))
            return
        self.saved_tof = record
        self.use_saved_tof.setEnabled(True)
        self.skips["tof"] = False
        self._refresh_indicators()
        QMessageBox.information(self, "ToF range calibration saved", "The sensor bias and offset profile passed held-out range checks and was saved. Verify facial eye-depth accuracy on the installed rig before reporting results.")

    def _skip(self, component):
        if component == "camera" and self.fit_worker and self.fit_worker.isRunning():
            self.camera_message.setText("Wait for the camera fit to finish before skipping it.")
            return
        if component == "camera" and not self._stop_camera():
            return
        if component == "tof" and self.sensor_worker and not self.sensor_worker.stop():
            return
        self.skips[component] = True
        self._refresh_indicators()

    def _use_saved(self, component):
        self.skips[component] = False
        self._refresh_indicators()

    def _reset_camera_views(self):
        if not self._stop_camera() or (self.fit_worker and self.fit_worker.isRunning()):
            return
        self.frames.clear()
        self.corners.clear()
        self.candidate = self.session_dir = None
        self.square.setEnabled(True)
        self.fit.setEnabled(False)
        self.save_camera.setEnabled(False)
        self.camera_message.setText("Camera samples reset. Saved profiles are preserved until a new successful Save.")

    def _reset_range_samples(self):
        self.range_samples.clear()
        self.recent.clear()
        self.range_message.setText("ToF samples reset. The saved range profile is preserved.")

    def done(self, result):
        if not self._stop_camera():
            return
        if self.fit_worker and self.fit_worker.isRunning():
            self.camera_message.setText("Wait for the current fit to finish before closing.")
            return
        if self.sensor_worker and not self.sensor_worker.stop():
            self.sensor_message.setText("Waiting for sensor release; try Close again.")
            return
        super().done(result)

    def closeEvent(self, event):
        event.ignore()
        self.reject()
