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
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
    QLabel, QLineEdit, QMessageBox, QTabWidget,
    QVBoxLayout, QWidget, QScrollArea, QFrame,
)

from glare_tracker.calibration import _calibration_dir
from glare_tracker.installation import camera_model, camera_record, fit_tof, validate_tof_profile
from glare_tracker.tof import ToFSerialWorker
from glare_tracker.widgets.stereo_calibration import (
    MIN_SAMPLES, SingleBoardCapture, SingleBoardFit,
    calibration_guide_asset_path, printable_chessboard_path,
)
from glare_tracker.widgets.calibration_guide import (
    CalibrationActions, CalibrationGuideDialog, DRIVER_STEPS, TOF_STEPS, size_calibration_dialog,
)
from glare_tracker.widgets.icons import command_button


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


class DriverCalibrationGuide(CalibrationGuideDialog):
    def __init__(self, parent=None, *, current=0):
        pictures = "".join(
            f'<p><img width="440" src="{calibration_guide_asset_path(asset).as_uri()}"></p>'
            for asset in ("flat_board.svg", "pose_coverage.svg")
        )
        sections = (("1. Camera", DRIVER_STEPS + pictures), ("2. ToF sensor", TOF_STEPS))
        super().__init__("Driver calibration guide", sections, parent, current=current)


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
        size_calibration_dialog(self, 880, 750)
        layout = QVBoxLayout(self)
        self.camera_indicator = note("")
        self.tof_indicator = note("")
        layout.addWidget(self.camera_indicator)
        layout.addWidget(self.tof_indicator)
        layout.addWidget(note(
            "Set up the driver camera first. If you have no distance sensor controller, "
            "open the ToF tab and select Skip ToF for now."))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._camera_page(), "1. Driver camera")
        self.tabs.addTab(self._tof_page(), "2. ToF sensor")
        layout.addWidget(self.tabs, 1)
        self.guide = command_button("Camera and ToF guide...", "help", role="guide")
        self.print_board = command_button("Print A4 chessboard...", "print")
        close = command_button("Close", "close")
        self.guide.clicked.connect(
            lambda: DriverCalibrationGuide(self, current=self.tabs.currentIndex()).exec_())
        self.print_board.clicked.connect(self._print)
        close.clicked.connect(self.reject)
        layout.addLayout(CalibrationActions(self.guide, self.print_board, close))
        self._refresh_indicators()

    def _refresh_indicators(self):
        self.camera_indicator.setText("CAMERA: " + ("SKIPPED for this session" if self.skips["camera"] else
            "Calibrated (lens fit saved; installed pose is separate)" if self.saved_camera else "Not calibrated"))
        self.tof_indicator.setText("ToF: " + ("SKIPPED - fixed/IPD depth is chosen in Driver settings" if self.skips["tof"] else
            "Calibrated range profile saved; live connection still required" if self.saved_tof else "Not calibrated / not connected"))

    def _camera_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.addWidget(note(
            f"Driver camera {self.index}. Use the flat board with 9 by 6 inner corners. "
            "Measure the square before capture."))
        self.square = number(2., .1, 20.)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.addRow("Measured square side:", self.square)
        self.ipd = number(6.3, 3., 9.)
        form.addRow("Measured eye separation (IPD):", self.ipd)
        body_layout.addLayout(form)
        self.preview = QLabel("Camera preview starts only when requested")
        self.preview.setMinimumSize(420, 240)
        self.preview.setAlignment(Qt.AlignCenter)
        body_layout.addWidget(self.preview, 1)
        layout.addWidget(scroll_page(body), 1)
        self.camera_message = note(f"0 / {MIN_SAMPLES} varied views. Start the camera with a rigid flat board.")
        layout.addWidget(self.camera_message)
        self.start = command_button("Start camera", "play")
        self.take = command_button("Capture view", "camera")
        self.fit = command_button("Fit camera", "fit")
        self.save_camera = command_button("Save camera profile", "save", role="accent")
        self.skip_camera = command_button("Skip camera for now", "next")
        self.take.setEnabled(False)
        self.fit.setEnabled(False)
        self.save_camera.setEnabled(False)
        self.start.clicked.connect(self._start_camera)
        self.take.clicked.connect(lambda: self.capture_worker.capture_requested.set())
        self.fit.clicked.connect(self._fit_camera)
        self.save_camera.clicked.connect(self._save_camera)
        self.skip_camera.clicked.connect(lambda: self._skip("camera"))
        layout.addLayout(CalibrationActions(
            self.start, self.take, self.fit, self.save_camera, self.skip_camera))
        self.reset_camera = command_button("Reset captured camera views", "reset")
        self.use_saved_camera = command_button("Use saved camera profile", "folder")
        self.use_saved_camera.setEnabled(self.saved_camera is not None)
        self.reset_camera.clicked.connect(self._reset_camera_views)
        self.use_saved_camera.clicked.connect(lambda: self._use_saved("camera"))
        layout.addLayout(CalibrationActions(self.reset_camera, self.use_saved_camera))
        return page

    def _tof_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.addWidget(note(
            "If you have no distance sensor controller, select Skip ToF for now."))
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
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
        body_layout.addLayout(form)
        self.sensor_message = note("Distance sensor is disconnected.")
        self.range_message = note("No range samples captured")
        body_layout.addWidget(self.sensor_message)
        body_layout.addWidget(self.range_message)
        body_layout.addStretch()
        layout.addWidget(scroll_page(body), 1)
        self.connect_sensor = command_button("Connect / reconnect", "connect")
        self.capture_range = command_button("Capture 20 readings", "target")
        self.save_tof = command_button("Fit and Save ToF", "save", role="accent")
        self.skip_tof = command_button("Skip ToF for now", "next")
        self.connect_sensor.clicked.connect(self._connect_sensor)
        self.capture_range.clicked.connect(self._capture_range)
        self.save_tof.clicked.connect(self._save_tof)
        self.skip_tof.clicked.connect(lambda: self._skip("tof"))
        layout.addLayout(CalibrationActions(
            self.connect_sensor, self.capture_range, self.save_tof, self.skip_tof))
        self.reset_ranges = command_button("Reset captured ToF distances", "reset")
        self.use_saved_tof = command_button("Use saved ToF profile", "folder")
        self.use_saved_tof.setEnabled(self.saved_tof is not None)
        self.reset_ranges.clicked.connect(self._reset_range_samples)
        self.use_saved_tof.clicked.connect(lambda: self._use_saved("tof"))
        layout.addLayout(CalibrationActions(self.reset_ranges, self.use_saved_tof))
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
