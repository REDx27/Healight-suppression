"""Measured installed-camera poses and physical LCD pixel registration."""

import json

import cv2
import numpy as np
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from glare_tracker.installation import board_points, fit_installed_pose, fit_panel_mapping
from glare_tracker.widgets.calibration_guide import (
    CalibrationActions, CalibrationGuideDialog, LCD_STEPS, RIG_STEPS, VERIFY_STEPS,
    size_calibration_dialog,
)
from glare_tracker.widgets.driver_calibration import note, number, session_folder, scroll_page
from glare_tracker.widgets.icons import command_button
from glare_tracker.widgets.stereo_calibration import SingleBoardCapture


class FitJob(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.result.emit(self.function())
        except Exception as error:
            self.failed.emit(str(error))


class InstalledPosePage(QWidget):
    def __init__(self, side, index, model, parent=None):
        super().__init__(parent)
        self.side, self.index, self.model = side, index, model
        self.worker = self.fit_worker = None
        self.samples = []
        self.result = None
        self.archive = None
        self.frozen = False
        layout = QVBoxLayout(self)
        role = "Road LEFT" if side == "road" else "Driver"
        layout.addWidget(note(
            f"{role} camera {index}. Measure the first inner corner from the LCD bottom centre. "
            "Capture six fit placements at three or more depths, then three new validation placements."))
        form = QFormLayout()
        self.square = number(2., .1, 20.)
        form.addRow("Measured square side:", self.square)
        self.origin = [number(-10 if side == "road" else 10), number(100 if side == "road" else -50), number(20)]
        self.angles = [number(0, -180, 180, " deg") for _ in range(3)]
        for label, widgets in (("First inner corner", self.origin), ("Measured rotations", self.angles)):
            row = QHBoxLayout()
            for axis, widget in zip("XYZ", widgets):
                row.addWidget(QLabel(axis))
                row.addWidget(widget)
            form.addRow(label + ":", row)
        self.split = QComboBox()
        self.split.addItems(["fit", "validation"])
        form.addRow("Placement use:", self.split)
        self.reverse = QCheckBox("Reverse detected corner order (180 degrees)")
        self.confirm = QCheckBox("The measurements and marked corner match this view")
        form.addRow(self.reverse)
        form.addRow(self.confirm)
        layout.addLayout(form)
        self.preview = QLabel("Native unmirrored preview; camera starts on request")
        self.preview.setMinimumSize(400, 180)
        self.preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview, 1)
        self.message = note("No measured placements captured")
        layout.addWidget(self.message)
        self.start = command_button("Start preview", "play")
        self.capture = command_button("Capture measured placement", "camera")
        self.fit = command_button("Fit / validate installed pose", "fit")
        self.undo = command_button("Undo last placement", "undo")
        self.capture.setEnabled(False)
        self.fit.setEnabled(False)
        self.start.setEnabled(model is not None)
        self.start.clicked.connect(self._start)
        self.capture.clicked.connect(self._capture)
        self.fit.clicked.connect(self._fit)
        layout.addLayout(CalibrationActions(self.start, self.capture, self.fit))
        self.undo.clicked.connect(self._undo)
        layout.addWidget(self.undo)
        if model is None:
            self.message.setText("Save the component camera calibration first. This side cannot be fitted from an assumed lens model.")

    def _start(self):
        if self.worker and self.worker.isRunning() and self.frozen:
            self.frozen = False
            self.start.setText("Start preview")
            self.capture.setEnabled(True)
            return
        if not self.stop() or (self.fit_worker and self.fit_worker.isRunning()):
            return
        try:
            if self.archive is None:
                self.archive = session_folder(self.side + "_pose")
        except OSError as error:
            self.message.setText(str(error))
            return
        self.worker = SingleBoardCapture(self.index, (9, 6), self.side, self)
        worker = self.worker
        self.frozen = False
        self.worker.preview.connect(lambda image: self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            700, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if worker is self.worker and not self.frozen else None)
        self.worker.status.connect(self.message.setText)
        self.worker.sample.connect(lambda sample: self._sample(sample) if worker is self.worker else None)
        self.worker.capture_finished.connect(lambda: self._capture_finished() if worker is self.worker else None)
        self.worker.finished.connect(lambda: self.capture.setEnabled(False) if worker is self.worker else None)
        self.worker.start()
        self.capture.setEnabled(True)

    def _capture(self):
        if not self.worker or not self.worker.isRunning() or hasattr(self, "pending"):
            return
        if not self.confirm.isChecked():
            self.message.setText("Measure the pose and confirm the marked first inner corner before capturing.")
            return
        self.pending = {"origin": [s.value() for s in self.origin],
                        "angles": [s.value() for s in self.angles],
                        "square_cm": self.square.value(), "split": self.split.currentText(),
                        "reverse": self.reverse.isChecked()}
        self.confirm.setChecked(False)
        self.capture.setEnabled(False)
        self.worker.capture_requested.set()

    def _capture_finished(self):
        if hasattr(self, "pending"):
            del self.pending
        self.capture.setEnabled(bool(self.worker and self.worker.isRunning() and not self.frozen))

    def _sample(self, payload):
        if not hasattr(self, "pending"):
            return
        pending = self.pending
        del self.pending
        frame, corners = payload
        if (frame.shape[1], frame.shape[0]) != self.model.image_size:
            self.message.setText("Native capture size differs from the lens profile. Recalibrate the lens at this mode.")
            return
        pixels = corners.reshape(-1, 2)
        if pending["reverse"]:
            pixels = pixels[::-1]
        shown = frame.copy()
        cv2.drawChessboardCorners(shown, (9, 6), pixels.astype(np.float32).reshape(-1, 1, 2), True)
        cv2.putText(shown, "1", tuple(pixels[0].astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        from glare_tracker.widgets.stereo_calibration import _image
        self.preview.setPixmap(QPixmap.fromImage(_image(shown)).scaled(700, 240, Qt.KeepAspectRatio))
        self.frozen = True
        self.start.setText("Resume preview")
        key = pending["origin"] + pending["angles"]
        if any(s["pose_key"] == key for s in self.samples):
            self.message.setText("Measured placement already exists; use a new fit/validation placement.")
            return
        points = board_points((9, 6), pending["square_cm"], pending["origin"], pending["angles"], self.side)
        record = {**pending, "pose_key": key, "points_cm": points.tolist(), "pixels": pixels.tolist()}
        try:
            if not cv2.imwrite(str(self.archive / f"{len(self.samples):03}_{pending['split']}.png"), frame):
                raise OSError("Image writer failed")
            (self.archive / f"{len(self.samples):03}.json").write_text(json.dumps(record, indent=2))
        except OSError as error:
            self.message.setText(str(error))
            return
        self.samples.append(record)
        self.result = None
        count = sum(s["split"] == "fit" for s in self.samples)
        validation = len(self.samples) - count
        self.message.setText(f"{count}/6 fit, {validation}/3 validation placements. Inspect corner 1 on the saved capture.")
        self.fit.setEnabled(count >= 6 and validation >= 3)

    def _fit(self):
        if not self.stop():
            return
        samples = json.loads(json.dumps(self.samples))
        self.fit.setEnabled(False)
        self.start.setEnabled(False)
        self.undo.setEnabled(False)
        self.result = None
        self.fit_worker = FitJob(lambda: fit_installed_pose(samples, self.model, self.side), self)
        self.fit_worker.result.connect(self._fitted)
        self.fit_worker.failed.connect(self.message.setText)
        self.fit_worker.finished.connect(lambda: (self.fit.setEnabled(True), self.start.setEnabled(True), self.undo.setEnabled(True)))
        self.fit_worker.start()

    def _fitted(self, result):
        result["evidence"] = str(self.archive)
        self.result = result
        report = result["report"]
        self.message.setText(f"POSE PASSED: fit RMS {report['fit_rmse_px']:.3f} px; held-out RMS "
                             f"{report['held_out_rmse_px']:.3f} px; max ray error "
                             f"{report['held_out_max_transverse_cm']:.3f} cm. Complete LCD mapping, then save the rig.")

    def _undo(self):
        if self.fit_worker and self.fit_worker.isRunning():
            return
        if self.samples:
            self.samples.pop()
        self.result = None
        self.fit.setEnabled(False)
        self.message.setText(f"{len(self.samples)} placements remain. Resume preview and recapture the measured placement.")

    def stop(self):
        if hasattr(self, "pending"):
            del self.pending
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            if not self.worker.wait(5000):
                self.message.setText("Waiting for camera release; try again shortly.")
                return False
        self.capture.setEnabled(False)
        return True

    def can_close(self):
        return self.stop() and not (self.fit_worker and self.fit_worker.isRunning())


class PanelMappingPage(QWidget):
    TARGETS = ((.1, .1), (.9, .1), (.1, .9), (.9, .9), (.5, .1), (.5, .9),
               (.1, .5), (.5, .5), (.9, .5))

    def __init__(self, width_cm, height_cm, show_mark, parent=None):
        super().__init__(parent)
        self.width, self.height, self.show_mark = width_cm, height_cm, show_mark
        self.samples = []
        self.result = None
        self.shown_index = None
        layout = QVBoxLayout(self)
        layout.addWidget(note(
            "Show each dot on the secondary LCD. Use a ruler to measure sideways (X) "
            "and up (Z) from the bottom centre. Capture all nine dots."))
        form = QFormLayout()
        self.target = QComboBox()
        self.target.addItems([f"{i + 1}: {'FIT' if i < 6 else 'VALIDATION'} ({u:.1f}, {v:.1f})"
                              for i, (u, v) in enumerate(self.TARGETS)])
        self.x = number(0.)
        self.z = number(0.)
        self.confirm = QCheckBox("I measured this mark on the actual LCD active area")
        form.addRow("Target:", self.target)
        form.addRow("Measured X:", self.x)
        form.addRow("Measured Z:", self.z)
        form.addRow(self.confirm)
        layout.addLayout(form)
        self.show = command_button("Show mark on selected LCD", "display")
        self.take = command_button("Capture measured mark", "target")
        self.fit = command_button("Fit / validate LCD mapping", "fit")
        self.undo = command_button("Undo last mark", "undo")
        layout.addLayout(CalibrationActions(self.show, self.take, self.fit))
        self.undo.clicked.connect(self._undo)
        layout.addWidget(self.undo)
        self.message = note("0/9 physical LCD marks captured")
        layout.addWidget(self.message)
        self.show.clicked.connect(self._show)
        self.take.clicked.connect(self._capture)
        self.fit.clicked.connect(self._fit)
        self.target.currentIndexChanged.connect(lambda: self.confirm.setChecked(False))
        layout.addStretch()

    def _show(self):
        if self.show_mark(self.TARGETS[self.target.currentIndex()]):
            self.shown_index = self.target.currentIndex()
            self.message.setText("Measure the displayed mark's X/Z, then confirm and capture.")
        else:
            self.shown_index = None
            self.message.setText("No usable secondary LCD selected. Connect it in Extended Desktop mode and select it in output settings.")

    def _capture(self):
        index = self.target.currentIndex()
        if self.shown_index != index or not self.confirm.isChecked():
            self.message.setText("Show this target on the LCD, then measure and confirm it.")
            return
        if any(s["uv"] == list(self.TARGETS[index]) for s in self.samples):
            self.message.setText("That target is already captured. Select another target.")
            return
        self.samples.append({"uv": list(self.TARGETS[index]), "xz_cm": [self.x.value(), self.z.value()],
                             "split": "fit" if index < 6 else "validation"})
        self.confirm.setChecked(False)
        self.result = None
        self.message.setText(f"{len(self.samples)}/9 marks captured")
        self.target.setCurrentIndex(min(index + 1, 8))

    def _fit(self):
        self.result = None
        try:
            self.result = fit_panel_mapping(self.samples, self.width, self.height)
            self.result["measurements"] = json.loads(json.dumps(self.samples))
            self.message.setText(f"LCD mapping PASSED. Held-out max error {self.result['max_error_cm']:.3f} cm. Save the installed rig profile.")
        except ValueError as error:
            self.message.setText(str(error))

    def _undo(self):
        if self.samples:
            removed = self.samples.pop()
            self.target.setCurrentIndex(self.TARGETS.index(tuple(removed["uv"])))
        self.result = None
        self.shown_index = None
        self.confirm.setChecked(False)
        self.message.setText(f"{len(self.samples)}/9 marks remain. Show and remeasure the target.")


class RigCalibrationDialog(QDialog):
    def __init__(self, setup, models, store, show_mark, parent=None):
        super().__init__(parent)
        self.setup, self.store = setup, store
        self.saved_profile = None
        self.setWindowTitle("Installed rig - camera to LCD calibration")
        size_calibration_dialog(self, 1000, 800)
        layout = QVBoxLayout(self)
        layout.addWidget(note(
            "Keep the cameras and LCD in their final mounts. Complete the camera tabs shown "
            "here, then measure the dots on the LCD. The guide shows where to put the board "
            "and where to start measuring."))
        form = QFormLayout()
        self.rig_id = QLineEdit("rig-v1")
        self.identity_confirm = QCheckBox("Camera order and mounts checked")
        form.addRow("Physical rig / mount revision:", self.rig_id)
        form.addRow(self.identity_confirm)
        layout.addLayout(form)
        self.tabs = QTabWidget()
        self.pages = {}
        for role in ("road", "driver"):
            if role not in models:
                continue
            index, model = models[role]
            page = InstalledPosePage(role, index, model, self)
            self.pages[role] = page
            self.tabs.addTab(scroll_page(page), f"{len(self.pages)}. {role.title()} installed pose")
        self.panel_page = PanelMappingPage(*setup["panel_cm"], show_mark, self)
        self.tabs.addTab(scroll_page(self.panel_page), f"{len(self.pages) + 1}. LCD physical mapping")
        layout.addWidget(self.tabs, 1)
        self.status = note("Not saved. Complete required camera poses and LCD mapping.")
        layout.addWidget(self.status)
        guide = command_button("Installed rig calibration guide...", "help", role="guide")
        self.save = command_button("Save installed rig profile", "save", role="accent")
        close = command_button("Close", "close")
        guide.clicked.connect(self._guide)
        self.save.clicked.connect(self._save)
        close.clicked.connect(self.reject)
        layout.addLayout(CalibrationActions(guide, self.save, close))
        self.tabs.currentChanged.connect(lambda _: self._stop_other_cameras())

    def _stop_other_cameras(self):
        for page in self.pages.values():
            if self.tabs.currentWidget().widget() is not page:
                page.stop()

    def _guide(self):
        sections = [("Installed rig", RIG_STEPS)] if self.pages else []
        current = len(sections) if self.tabs.currentIndex() == len(self.pages) else 0
        sections.extend((("LCD mapping", LCD_STEPS), ("Verify", VERIFY_STEPS)))
        CalibrationGuideDialog(
            "Installed rig calibration guide", sections, self, current=current).exec_()

    def _save(self):
        if not self.rig_id.text().strip() or not self.identity_confirm.isChecked():
            self.status.setText("Name the physical rig revision and confirm all camera identities/mounts.")
            return
        if any(page.result is None for page in self.pages.values()) or self.panel_page.result is None:
            self.status.setText("Fit every required installed camera pose and the actual LCD mapping before saving.")
            return
        profile = {"rig_id": self.rig_id.text().strip(), "binding": self.setup,
                   "poses": {role: page.result for role, page in self.pages.items()},
                   "panel": self.panel_page.result,
                   "validation_scope": "lens/pose transverse/pixel marks; verify final eye/light depth and attenuation independently"}
        try:
            self.store.save("rig", profile)
        except (ValueError, OSError) as error:
            self.status.setText(str(error))
            return
        self.saved_profile = profile
        self.status.setText("Installed rig profile SAVED. Return to the panel and confirm the unchanged installation before Run.")
        QMessageBox.information(self, "Installed rig calibration saved", "Required camera poses and LCD mapping passed and were saved. Independently check real dark-dot alignment before reporting physical accuracy.")

    def done(self, result):
        for page in self.pages.values():
            if not page.can_close():
                self.status.setText("Wait for camera release / the current pose fit, then close again.")
                return
        super().done(result)

    def closeEvent(self, event):
        event.ignore()
        self.reject()
