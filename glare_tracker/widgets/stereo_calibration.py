"""Paired, unmirrored chessboard capture and fitting for the road cameras."""

from datetime import datetime, timezone
import json
from threading import Event

import cv2
import numpy as np
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox,
)

from glare_tracker.capture import open_video_capture, configure_video_capture
from glare_tracker.calibration import (
    _calibration_dir, calibrate_stereo, detect_checkerboard,
    save_stereo_calibration, stereo_profile_name,
)


def calibration_quality(result, pairs, pattern, max_rms=1.5, max_row_error=2.0):
    """Fit diagnostics only; these do not constitute held-out physical accuracy."""
    errors = []
    for left, right in pairs:
        points = []
        for frame, camera, rotation, projection in (
            (left, result.cam1, result.R1, result.P1),
            (right, result.cam2, result.R2, result.P2),
        ):
            corners = detect_checkerboard(frame, pattern)
            if corners is None:
                raise ValueError("A saved pair no longer yields both chessboard detections")
            points.append(cv2.undistortPoints(
                corners, camera.camera_matrix, camera.dist_coeffs,
                R=rotation, P=projection).reshape(-1, 2))
        errors.extend(np.abs(points[0][:, 1] - points[1][:, 1]).tolist())
    row_p95 = float(np.percentile(errors, 95)) if errors else float("inf")
    matrices = (result.R, result.T, result.R1, result.R2, result.P1, result.P2, result.Q,
                result.cam1.camera_matrix, result.cam2.camera_matrix,
                result.cam1.dist_coeffs, result.cam2.dist_coeffs)
    passed = bool(
        all(np.isfinite(m).all() for m in matrices)
        and np.isfinite(result.rms_error) and result.rms_error <= max_rms
        and result.baseline_cm > 0
        and result.P2[0, 3] < 0  # supported horizontal left-to-right rig
        and row_p95 <= max_row_error)
    return {"passed": passed, "stereo_rms_px": float(result.rms_error),
            "baseline_cm": float(result.baseline_cm),
            "fit_rectified_row_p95_px": row_p95,
            "max_rms_px": max_rms, "max_row_p95_px": max_row_error,
            "note": "Fit-set diagnostics only; verify measured distances independently."}


class StereoBoardCapture(QThread):
    preview = pyqtSignal(QImage, QImage)
    status = pyqtSignal(str)
    sample = pyqtSignal(object)

    def __init__(self, indices, pattern, parent=None):
        super().__init__(parent)
        self.indices, self.pattern = indices, pattern
        self.capture_requested = Event()

    def run(self):
        captures = []
        try:
            for index in self.indices:
                cap, backend = open_video_capture(index)
                if cap is None:
                    raise RuntimeError(f"Camera {index} unavailable; close other camera apps")
                captures.append(cap)
                configure_video_capture(cap)
                self.status.emit(f"Camera {index} opened using {backend}")
            self.status.emit("Both feeds ready. Hold the board still, then Capture pair.")
            failures = 0
            while not self.isInterruptionRequested():
                ok1, ok2 = captures[0].grab(), captures[1].grab()
                ret1, left = captures[0].retrieve() if ok1 else (False, None)
                ret2, right = captures[1].retrieve() if ok2 else (False, None)
                if not (ret1 and ret2):
                    failures += 1
                    if failures == 1:
                        self.status.emit("Frame read failed; checking both cameras...")
                    if failures >= 30:
                        raise RuntimeError("Repeated camera read failures; reconnect and restart capture")
                    self.msleep(30)
                    continue
                failures = 0
                if left.shape != right.shape:
                    raise RuntimeError("Cameras negotiated different resolutions; use matching modes")
                show_left, show_right = left.copy(), right.copy()
                if self.capture_requested.is_set():
                    self.capture_requested.clear()
                    c1 = detect_checkerboard(left, self.pattern)
                    c2 = detect_checkerboard(right, self.pattern)
                    for frame, corners in ((show_left, c1), (show_right, c2)):
                        if corners is not None:
                            cv2.drawChessboardCorners(frame, self.pattern, corners, True)
                    if c1 is not None and c2 is not None:
                        self.sample.emit((left.copy(), right.copy(), c1, c2))
                    else:
                        self.status.emit(
                            f"Not saved: left board {'found' if c1 is not None else 'missing'}, "
                            f"right board {'found' if c2 is not None else 'missing'}")
                images = []
                for frame in (show_left, show_right):
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w = rgb.shape[:2]
                    images.append(QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888).copy())
                self.preview.emit(*images)
                self.msleep(60)
        except Exception as error:
            self.status.emit(str(error))
        finally:
            for cap in captures:
                cap.release()


class StereoBoardFit(QThread):
    result_ready = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def __init__(self, pairs, pattern, square_cm, indices, parent=None):
        super().__init__(parent)
        self.pairs, self.pattern = list(pairs), pattern
        self.square_cm, self.indices = square_cm, indices

    def run(self):
        try:
            result = calibrate_stereo(
                [p[0] for p in self.pairs], [p[1] for p in self.pairs],
                self.pattern, self.square_cm)
            if result is None:
                raise ValueError("Not enough usable paired chessboards")
            result.camera_indices = self.indices
            report = calibration_quality(result, self.pairs, self.pattern)
            self.result_ready.emit(result, report)
        except Exception as error:
            self.failed.emit(str(error))


class StereoCalibrationDialog(QDialog):
    """Owns camera capture only while the main application is stopped."""

    def __init__(self, primary, secondary, parent=None):
        super().__init__(parent)
        self.indices = (primary, secondary)
        self.capture_worker = self.fit_worker = None
        self.pairs, self.corner_pairs = [], []
        self.result = self.report = self.session_dir = None
        self.saved_path = None
        self.setWindowTitle("Road stereo — chessboard calibration")
        self.resize(900, 660)
        layout = QVBoxLayout(self)
        intro = QLabel(
            f"LEFT camera {primary} | RIGHT camera {secondary} (as viewed facing the scene).\n"
            "Fix both cameras and final filters rigidly. Lock focus/zoom. Use a flat board\n"
            "with a white border. Default: 10 × 7 squares = 9 × 6 INNER corners.\n"
            "Measure one printed square in cm. Capture at least 15 varied still poses,\n"
            "covering centre, edges, near/far and tilted views, visible in BOTH cameras.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.columns, self.rows = QSpinBox(), QSpinBox()
        for spin, value in ((self.columns, 9), (self.rows, 6)):
            spin.setRange(3, 20)
            spin.setValue(value)
        self.square = QDoubleSpinBox()
        self.square.setRange(0.1, 20)
        self.square.setDecimals(3)
        self.square.setValue(2.5)
        self.square.setSuffix(" cm")
        form.addRow("Inner corner columns:", self.columns)
        form.addRow("Inner corner rows:", self.rows)
        form.addRow("Measured square side:", self.square)
        layout.addLayout(form)
        previews = QHBoxLayout()
        self.left, self.right = QLabel("Left feed"), QLabel("Right feed")
        for label in (self.left, self.right):
            label.setMinimumSize(320, 240)
            label.setAlignment(Qt.AlignCenter)
            previews.addWidget(label)
        layout.addLayout(previews)
        self.counter = QLabel("0 / 15 minimum pairs")
        self.message = QLabel("Start capture after checking camera order and board dimensions.")
        self.message.setWordWrap(True)
        layout.addWidget(self.counter)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.start = QPushButton("Start capture")
        self.take = QPushButton("Capture pair")
        self.fit = QPushButton("Stop capture and fit")
        self.save = QPushButton("Save profile")
        close = QPushButton("Close")
        for button in (self.start, self.take, self.fit, self.save, close):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.take.setEnabled(False)
        self.fit.setEnabled(False)
        self.save.setEnabled(False)
        self.start.clicked.connect(self._start)
        self.take.clicked.connect(lambda: self.capture_worker.capture_requested.set())
        self.fit.clicked.connect(self._fit)
        self.save.clicked.connect(self._save)
        close.clicked.connect(self.reject)

    def _start(self):
        if self.indices[0] == self.indices[1]:
            self.message.setText("Select two different road cameras.")
            return
        try:
            self.session_dir = _calibration_dir() / "stereo_sessions" / datetime.now(
                timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            self.session_dir.mkdir(parents=True)
            metadata = {"camera_indices": self.indices,
                        "inner_corners": [self.columns.value(), self.rows.value()],
                        "square_size_cm": self.square.value(),
                        "note": "Sequential software grabs; hold the board stationary."}
            (self.session_dir / "setup.json").write_text(json.dumps(metadata, indent=2))
        except OSError as error:
            self.message.setText(f"Cannot create calibration session: {error}")
            return
        for widget in (self.start, self.columns, self.rows, self.square):
            widget.setEnabled(False)
        self.capture_worker = StereoBoardCapture(
            self.indices, (self.columns.value(), self.rows.value()), self)
        self.capture_worker.preview.connect(self._preview)
        self.capture_worker.status.connect(self.message.setText)
        self.capture_worker.sample.connect(self._sample)
        self.capture_worker.finished.connect(lambda: self.take.setEnabled(False))
        self.take.setEnabled(True)
        self.capture_worker.start()

    def _preview(self, left, right):
        for label, image in ((self.left, left), (self.right, right)):
            label.setPixmap(QPixmap.fromImage(image).scaled(
                400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _sample(self, payload):
        if self.fit_worker is not None:
            return
        left, right, c1, c2 = payload
        if any(max(np.sqrt(np.mean((c1 - a) ** 2)),
                   np.sqrt(np.mean((c2 - b) ** 2))) < 8
               for a, b in self.corner_pairs):
            self.message.setText("Similar pose already saved. Move or tilt the board before capturing.")
            return
        index = len(self.pairs) + 1
        try:
            for side, frame in (("left", left), ("right", right)):
                if not cv2.imwrite(str(self.session_dir / f"{index:03}_{side}.png"), frame):
                    raise OSError("Image writer failed")
        except (OSError, cv2.error) as error:
            self.message.setText(f"Pair not accepted: {error}")
            return
        self.pairs.append((left, right))
        self.corner_pairs.append((c1, c2))
        self.counter.setText(f"{index} / 15 minimum pairs")
        self.message.setText(f"Pair {index} saved. Move/tilt board; keep both cameras fixed.")
        self.fit.setEnabled(index >= 15)

    def _stop_capture(self):
        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.requestInterruption()
            if not self.capture_worker.wait(5000):
                self.message.setText("Waiting for camera driver to release; try Close again shortly.")
                return False
        return True

    def _fit(self):
        if not self._stop_capture():
            return
        self.take.setEnabled(False)
        self.fit.setEnabled(False)
        self.message.setText("Fitting camera intrinsics and stereo pose…")
        self.fit_worker = StereoBoardFit(
            self.pairs, (self.columns.value(), self.rows.value()), self.square.value(),
            self.indices, self)
        self.fit_worker.result_ready.connect(self._fit_done)
        self.fit_worker.failed.connect(self.message.setText)
        self.fit_worker.start()

    def _fit_done(self, result, report):
        self.result, self.report = result, report
        try:
            (self.session_dir / "report.json").write_text(json.dumps(report, indent=2))
        except OSError as error:
            self.message.setText(f"Cannot save fit report: {error}")
            return
        self.message.setText(
            f"Stereo RMS {report['stereo_rms_px']:.3f} px; "
            f"row error p95 {report['fit_rectified_row_p95_px']:.3f} px; "
            f"baseline {report['baseline_cm']:.2f} cm. "
            + ("Check baseline against ruler, then save. Verify known distances next."
               if report['passed'] else
               "Not accepted. Check left/right order, square size, focus and pose variety; collect a new set."))
        self.save.setEnabled(report['passed'])

    def _save(self):
        if not self.result or not self.report or not self.report['passed']:
            return
        try:
            name = stereo_profile_name(*self.indices)
            # Preserve every accepted candidate alongside its input frames/report.
            archive_name = f"stereo_sessions/{self.session_dir.name}/accepted"
            save_stereo_calibration(self.result, archive_name)
            self.saved_path = save_stereo_calibration(self.result, name)
            self.message.setText(f"Saved {self.saved_path}. Close, then Run to load it.")
            self.save.setEnabled(False)
        except Exception as error:
            self.message.setText(f"Save failed: {error}")

    def done(self, code):
        if self.fit_worker and self.fit_worker.isRunning():
            self.message.setText("Calibration is still fitting; close after it finishes.")
            return
        if self._stop_capture():
            super().done(code)

    def closeEvent(self, event):
        event.ignore()
        self.reject()
