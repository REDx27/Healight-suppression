"""Guided individual and stereo checkerboard calibration for the road cameras."""

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

from glare_tracker.capture import open_video_capture, configure_road_stereo_capture
from glare_tracker.calibration import (
    _calibration_dir, calibrate_single, calibrate_stereo_with_intrinsics,
    detect_checkerboard, save_single_calibration, save_stereo_calibration,
    stereo_profile_name,
)


MIN_SAMPLES = 15


def _image(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    return QImage(
        rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()


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
                raise ValueError("A saved pair no longer yields both checkerboard detections")
            points.append(cv2.undistortPoints(
                corners, camera.camera_matrix, camera.dist_coeffs,
                R=rotation, P=projection).reshape(-1, 2))
        errors.extend(np.abs(points[0][:, 1] - points[1][:, 1]).tolist())
    row_p95 = float(np.percentile(errors, 95)) if errors else float("inf")
    matrices = (result.R, result.T, result.R1, result.R2, result.P1, result.P2, result.Q,
                result.cam1.camera_matrix, result.cam2.camera_matrix,
                result.cam1.dist_coeffs, result.cam2.dist_coeffs)
    passed = bool(
        all(np.isfinite(matrix).all() for matrix in matrices)
        and np.isfinite(result.rms_error) and result.rms_error <= max_rms
        and result.baseline_cm > 0
        and result.P2[0, 3] < 0
        and row_p95 <= max_row_error)
    return {"passed": passed, "stereo_rms_px": float(result.rms_error),
            "baseline_cm": float(result.baseline_cm),
            "fit_rectified_row_p95_px": row_p95,
            "max_rms_px": max_rms, "max_row_p95_px": max_row_error,
            "note": "Fit-set diagnostics only; verify measured distances independently."}


class SingleBoardCapture(QThread):
    preview = pyqtSignal(QImage)
    status = pyqtSignal(str)
    sample = pyqtSignal(object)

    def __init__(self, index, pattern, side, parent=None):
        super().__init__(parent)
        self.index, self.pattern, self.side = index, pattern, side
        self.capture_requested = Event()

    def run(self):
        capture = None
        try:
            capture, backend = open_video_capture(self.index)
            if capture is None:
                raise RuntimeError(f"Camera {self.index} unavailable; close other camera apps")
            configure_road_stereo_capture(capture)
            self.status.emit(
                f"{self.side.upper()} camera {self.index} opened using {backend}. "
                "Move the board to a varied pose, then capture.")
            failures = 0
            while not self.isInterruptionRequested():
                ok, frame = capture.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= 30:
                        raise RuntimeError("Repeated camera read failures; reconnect and retry")
                    self.msleep(30)
                    continue
                failures = 0
                shown = frame.copy()
                if self.capture_requested.is_set():
                    self.capture_requested.clear()
                    corners = detect_checkerboard(frame, self.pattern)
                    if corners is None:
                        self.status.emit("Not saved: checkerboard inner corners were not all visible")
                    else:
                        cv2.drawChessboardCorners(shown, self.pattern, corners, True)
                        self.sample.emit((frame.copy(), corners))
                self.preview.emit(_image(shown))
                self.msleep(60)
        except Exception as error:
            self.status.emit(str(error))
        finally:
            if capture is not None:
                capture.release()


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
                capture, backend = open_video_capture(index)
                if capture is None:
                    raise RuntimeError(f"Camera {index} unavailable; close other camera apps")
                captures.append(capture)
                configure_road_stereo_capture(capture)
                self.status.emit(f"Camera {index} opened using {backend}")
            self.status.emit("Both feeds ready. Hold the board still, then capture a pair.")
            failures = 0
            while not self.isInterruptionRequested():
                ok1, ok2 = captures[0].grab(), captures[1].grab()
                ret1, left = captures[0].retrieve() if ok1 else (False, None)
                ret2, right = captures[1].retrieve() if ok2 else (False, None)
                if not (ret1 and ret2):
                    failures += 1
                    if failures >= 30:
                        raise RuntimeError("Repeated camera read failures; reconnect and retry")
                    self.msleep(30)
                    continue
                failures = 0
                if left.shape != right.shape:
                    raise RuntimeError("Cameras negotiated different resolutions; use matching modes")
                shown_left, shown_right = left.copy(), right.copy()
                if self.capture_requested.is_set():
                    self.capture_requested.clear()
                    corners1 = detect_checkerboard(left, self.pattern)
                    corners2 = detect_checkerboard(right, self.pattern)
                    for frame, corners in ((shown_left, corners1), (shown_right, corners2)):
                        if corners is not None:
                            cv2.drawChessboardCorners(frame, self.pattern, corners, True)
                    if corners1 is not None and corners2 is not None:
                        self.sample.emit((left.copy(), right.copy(), corners1, corners2))
                    else:
                        self.status.emit(
                            f"Not saved: left board {'found' if corners1 is not None else 'missing'}, "
                            f"right board {'found' if corners2 is not None else 'missing'}")
                self.preview.emit(_image(shown_left), _image(shown_right))
                self.msleep(60)
        except Exception as error:
            self.status.emit(str(error))
        finally:
            for capture in captures:
                capture.release()


class SingleBoardFit(QThread):
    result_ready = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, frames, pattern, square_cm, parent=None):
        super().__init__(parent)
        self.frames, self.pattern, self.square_cm = list(frames), pattern, square_cm

    def run(self):
        try:
            result = calibrate_single(self.frames, self.pattern, self.square_cm)
            if result is None:
                raise ValueError("Not enough usable checkerboard views")
            if not np.isfinite(result.rms_error) or result.rms_error > 1.5:
                raise ValueError(
                    f"Intrinsic RMS {result.rms_error:.3f} px is above 1.5 px; "
                    "capture sharper and more varied views")
            self.result_ready.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class StereoBoardFit(QThread):
    result_ready = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def __init__(self, pairs, pattern, square_cm, indices, intrinsics=None, parent=None):
        super().__init__(parent)
        self.pairs, self.pattern = list(pairs), pattern
        self.square_cm, self.indices = square_cm, indices
        self.intrinsics = intrinsics

    def run(self):
        try:
            if not self.intrinsics or any(value is None for value in self.intrinsics):
                raise ValueError("Fit LEFT and RIGHT individual calibrations first")
            result = calibrate_stereo_with_intrinsics(
                [pair[0] for pair in self.pairs], [pair[1] for pair in self.pairs],
                self.intrinsics[0], self.intrinsics[1], self.pattern, self.square_cm)
            if result is None:
                raise ValueError("Not enough usable paired checkerboards")
            result.camera_indices = self.indices
            report = calibration_quality(result, self.pairs, self.pattern)
            self.result_ready.emit(result, report)
        except Exception as error:
            self.failed.emit(str(error))


class StereoCalibrationDialog(QDialog):
    """Guide the operator through LEFT, RIGHT, then paired stereo fitting."""

    def __init__(self, primary, secondary, parent=None):
        super().__init__(parent)
        self.indices = (primary, secondary)
        self.stage = "left"
        self.capture_worker = self.fit_worker = None
        self.individual_frames = {"left": [], "right": []}
        self.individual_corners = {"left": [], "right": []}
        self.intrinsics = {"left": None, "right": None}
        self.pairs, self.corner_pairs = [], []
        self.result = self.report = self.session_dir = None
        self.saved_path = None
        self.setWindowTitle("Road cameras - guided calibration")
        self.resize(900, 680)
        layout = QVBoxLayout(self)
        self.intro = QLabel(
            f"Step 1 of 3: calibrate LEFT road camera {primary} without the dark filter.\n"
            f"Then calibrate RIGHT camera {secondary}, followed by the fixed stereo pair. "
            "Do not move either camera after the stereo stage. Use a flat board with a white border; "
            "10 x 7 squares means 9 x 6 INNER corners.")
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
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
        self.left, self.right = QLabel("LEFT feed"), QLabel("RIGHT: starts in step 2")
        for label in (self.left, self.right):
            label.setMinimumSize(320, 240)
            label.setAlignment(Qt.AlignCenter)
            previews.addWidget(label)
        layout.addLayout(previews)
        self.counter = QLabel(f"0 / {MIN_SAMPLES} minimum LEFT views")
        self.message = QLabel(
            "Measure the printed square, check LEFT/RIGHT indices, then start LEFT calibration.")
        self.message.setWordWrap(True)
        layout.addWidget(self.counter)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.start = QPushButton("Start LEFT calibration")
        self.take = QPushButton("Capture LEFT view")
        self.fit = QPushButton("Fit LEFT intrinsics")
        self.save = QPushButton("Save stereo profile")
        close = QPushButton("Close")
        for button in (self.start, self.take, self.fit, self.save, close):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.take.setEnabled(False)
        self.fit.setEnabled(False)
        self.save.setEnabled(False)
        self.start.clicked.connect(self._start)
        self.take.clicked.connect(self._request_capture)
        self.fit.clicked.connect(self._fit)
        self.save.clicked.connect(self._save)
        close.clicked.connect(self.reject)

    @property
    def pattern(self):
        return self.columns.value(), self.rows.value()

    def _ensure_session(self):
        if self.session_dir is not None:
            return True
        try:
            self.session_dir = _calibration_dir() / "stereo_sessions" / datetime.now(
                timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            self.session_dir.mkdir(parents=True)
            metadata = {"camera_indices": self.indices,
                        "inner_corners": list(self.pattern),
                        "square_size_cm": self.square.value(),
                        "stages": ["left_intrinsic", "right_intrinsic", "stereo"],
                        "filter_state": "calibrate without dark filters; verify again after fitting",
                        "note": "Sequential software grabs; hold the board stationary."}
            (self.session_dir / "setup.json").write_text(json.dumps(metadata, indent=2))
            return True
        except OSError as error:
            self.message.setText(f"Cannot create calibration session: {error}")
            self.session_dir = None
            return False

    def _start(self):
        if self.indices[0] == self.indices[1]:
            self.message.setText("Select two different road cameras.")
            return
        if not self._ensure_session():
            return
        for widget in (self.start, self.columns, self.rows, self.square):
            widget.setEnabled(False)
        if self.stage in ("left", "right"):
            index = self.indices[0 if self.stage == "left" else 1]
            self.capture_worker = SingleBoardCapture(index, self.pattern, self.stage, self)
            self.capture_worker.preview.connect(self._single_preview)
            self.capture_worker.sample.connect(self._sample_single)
        else:
            self.capture_worker = StereoBoardCapture(self.indices, self.pattern, self)
            self.capture_worker.preview.connect(self._preview)
            self.capture_worker.sample.connect(self._sample)
        self.capture_worker.status.connect(self.message.setText)
        self.capture_worker.finished.connect(lambda: self.take.setEnabled(False))
        self.take.setEnabled(True)
        self.capture_worker.start()

    def _request_capture(self):
        if self.capture_worker is not None:
            self.capture_worker.capture_requested.set()

    def _single_preview(self, image):
        label = self.left if self.stage == "left" else self.right
        label.setPixmap(QPixmap.fromImage(image).scaled(
            400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _preview(self, left, right):
        for label, image in ((self.left, left), (self.right, right)):
            label.setPixmap(QPixmap.fromImage(image).scaled(
                400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _sample_single(self, payload):
        if self.fit_worker is not None:
            return
        frame, corners = payload
        previous = self.individual_corners[self.stage]
        if any(np.sqrt(np.mean((corners - saved) ** 2)) < 8 for saved in previous):
            self.message.setText("Similar pose already saved. Move or tilt the board before capturing.")
            return
        sample_number = len(previous) + 1
        try:
            path = self.session_dir / f"{self.stage}_{sample_number:03}.png"
            if not cv2.imwrite(str(path), frame):
                raise OSError("Image writer failed")
        except (OSError, cv2.error) as error:
            self.message.setText(f"View not accepted: {error}")
            return
        self.individual_frames[self.stage].append(frame)
        previous.append(corners)
        side = self.stage.upper()
        self.counter.setText(f"{sample_number} / {MIN_SAMPLES} minimum {side} views")
        self.message.setText(
            f"{side} view {sample_number} saved. Cover centre, edges, near/far and tilted views.")
        self.fit.setEnabled(sample_number >= MIN_SAMPLES)

    def _sample(self, payload):
        """Accept one paired sample; kept public for camera-free regression tests."""
        if self.fit_worker is not None:
            return
        left, right, corners1, corners2 = payload
        if any(max(np.sqrt(np.mean((corners1 - saved1) ** 2)),
                   np.sqrt(np.mean((corners2 - saved2) ** 2))) < 8
               for saved1, saved2 in self.corner_pairs):
            self.message.setText("Similar pose already saved. Move or tilt the board before capturing.")
            return
        sample_number = len(self.pairs) + 1
        try:
            for side, frame in (("left", left), ("right", right)):
                if not cv2.imwrite(
                        str(self.session_dir / f"{sample_number:03}_{side}.png"), frame):
                    raise OSError("Image writer failed")
        except (OSError, cv2.error) as error:
            self.message.setText(f"Pair not accepted: {error}")
            return
        self.pairs.append((left, right))
        self.corner_pairs.append((corners1, corners2))
        self.counter.setText(f"{sample_number} / {MIN_SAMPLES} minimum stereo pairs")
        self.message.setText(
            f"Pair {sample_number} saved. Move/tilt the board; keep both cameras fixed.")
        self.fit.setEnabled(sample_number >= MIN_SAMPLES)

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
        if self.stage in ("left", "right"):
            self.message.setText(f"Fitting {self.stage.upper()} camera intrinsics...")
            self.fit_worker = SingleBoardFit(
                self.individual_frames[self.stage], self.pattern, self.square.value(), self)
            self.fit_worker.result_ready.connect(self._single_fit_done)
        else:
            self.message.setText("Fitting fixed stereo geometry...")
            self.fit_worker = StereoBoardFit(
                self.pairs, self.pattern, self.square.value(), self.indices,
                (self.intrinsics["left"], self.intrinsics["right"]), self)
            self.fit_worker.result_ready.connect(self._fit_done)
        self.fit_worker.failed.connect(self._fit_failed)
        self.fit_worker.start()

    def _fit_failed(self, message):
        self.fit_worker = None
        self.message.setText(f"Fit failed: {message}. Capture more varied views and retry.")
        self.start.setText(f"Capture more {self.stage.upper()} views")
        self.start.setEnabled(True)
        count = len(self.pairs) if self.stage == "stereo" else len(self.individual_frames[self.stage])
        self.fit.setEnabled(count >= MIN_SAMPLES)

    def _single_fit_done(self, result):
        completed = self.stage
        self.intrinsics[completed] = result
        try:
            save_single_calibration(
                result, f"stereo_sessions/{self.session_dir.name}/{completed}_intrinsic")
            report = {"stage": completed, "rms_px": float(result.rms_error),
                      "image_size": list(result.image_size), "samples": len(
                          self.individual_frames[completed])}
            (self.session_dir / f"{completed}_report.json").write_text(
                json.dumps(report, indent=2))
        except OSError as error:
            self.message.setText(f"Cannot archive {completed} calibration: {error}")
            self.fit_worker = None
            return
        self.fit_worker = None
        self.capture_worker = None
        if completed == "left":
            self.stage = "right"
            self.intro.setText(
                f"Step 2 of 3: LEFT passed at {result.rms_error:.3f} px. "
                f"Now calibrate RIGHT road camera {self.indices[1]} without the dark filter.")
            self.right.setText("RIGHT feed")
        else:
            self.stage = "stereo"
            self.intro.setText(
                "Step 3 of 3: both individual calibrations passed. Rigidly fix both cameras, "
                "confirm LEFT/RIGHT order, and capture the same stationary board in BOTH feeds.")
        label = self.stage.upper()
        self.counter.setText(f"0 / {MIN_SAMPLES} minimum {label} "
                             + ("pairs" if self.stage == "stereo" else "views"))
        self.start.setText(f"Start {label} calibration")
        self.take.setText("Capture pair" if self.stage == "stereo" else f"Capture {label} view")
        self.fit.setText("Fit stereo geometry" if self.stage == "stereo" else f"Fit {label} intrinsics")
        self.start.setEnabled(True)
        self.message.setText(
            f"{completed.upper()} intrinsics passed. Continue to {label} calibration.")

    def _fit_done(self, result, report):
        self.fit_worker = None
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
            + ("Check baseline against a ruler, then save. Apply filters only after this; "
               "the filtered setup must pass a geometric verification before measurements."
               if report["passed"] else
               "Not accepted. Check order, square size, focus, rigidity and pose variety."))
        self.save.setEnabled(report["passed"])

    def _save(self):
        if not self.result or not self.report or not self.report["passed"]:
            return
        try:
            name = stereo_profile_name(*self.indices)
            archive_name = f"stereo_sessions/{self.session_dir.name}/accepted"
            save_stereo_calibration(self.result, archive_name)
            self.saved_path = save_stereo_calibration(self.result, name)
            self.message.setText(
                f"Saved {self.saved_path}. Apply the dark filters without moving cameras, "
                "then perform the post-filter verification before collecting measurements.")
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
