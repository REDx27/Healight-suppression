"""Guided individual and stereo checkerboard calibration for the road cameras."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from threading import Event

import cv2
import numpy as np
from PyQt5.QtCore import QThread, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QMessageBox, QScrollArea, QWidget, QSizePolicy,
)

from glare_tracker.capture import open_video_capture, configure_road_stereo_capture, configure_video_capture
from glare_tracker.calibration import (
    _calibration_dir, calibrate_single, calibrate_stereo_with_intrinsics,
    detect_checkerboard, save_single_calibration, save_stereo_calibration,
    stereo_profile_name,
)
from glare_tracker.widgets.calibration_guide import (
    CalibrationActions, CalibrationGuideDialog, ROAD_STEPS, size_calibration_dialog,
)
from glare_tracker.widgets.icons import command_button


MIN_SAMPLES = 15
PRINTABLE_BOARD_NAME = "road_stereo_chessboard_A4_9x6_20mm.pdf"
GUIDE_ASSETS = (
    "flat_board.svg",
    "pose_coverage.svg",
    "stereo_sequence.svg",
    "stereo_capture.svg",
)


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def printable_chessboard_path() -> Path:
    """Locate the verified A4 board in source and packaged applications."""
    return _resource_root() / "output" / "pdf" / PRINTABLE_BOARD_NAME


def calibration_guide_asset_path(name: str) -> Path:
    """Locate one packaged visual calibration guide figure."""
    if name not in GUIDE_ASSETS:
        raise ValueError(f"Unknown calibration guide asset: {name}")
    return _resource_root() / "assets" / "calibration" / name


def _image(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    return QImage(
        rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888).copy()


class CalibrationPreview(QLabel):
    """Full native image, letterboxed into a layout-independent preview canvas."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.native_image = QImage()
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setAlignment(Qt.AlignCenter)

    def set_image(self, image):
        self.native_image = QImage(image)
        self._fit_image()

    def _fit_image(self):
        if not self.native_image.isNull():
            self.setPixmap(QPixmap.fromImage(self.native_image).scaled(
                self.contentsRect().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_image()


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


class CalibrationVisualGuideDialog(CalibrationGuideDialog):
    """Illustrated operator guide embedded in the calibration workflow."""

    SECTIONS = (
        (
            "Keep the checkerboard flat",
            "flat_board.svg",
            "Glue the print to stiff, flat backing. Keep the pattern and its "
            "white border clear of tape and fingers.",
        ),
        (
            "Move the checkerboard between pictures",
            "pose_coverage.svg",
            "Take sharp pictures at the centre, sides and corners. Bring the "
            "board near and far, and tilt it a little.",
        ),
        (
            "Work through LEFT, RIGHT and the pair",
            "stereo_sequence.svg",
            "Fit LEFT and RIGHT separately. Then fit the pair together and select "
            "Save stereo profile.",
        ),
        (
            "Keep the board still for paired pictures",
            "stereo_capture.svg",
            "Fix both cameras on one bar. Put the board on a stand, wait about "
            "one second after each move, then select Capture pair.",
        ),
    )

    def __init__(self, parent=None):
        super().__init__("Road stereo calibration guide", [("Steps", ROAD_STEPS)], parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for position, (title, asset, instructions) in enumerate(self.SECTIONS, start=1):
            heading = QLabel(f"<h2>{title}</h2>")
            content_layout.addWidget(heading)
            image_label = QLabel()
            image_label.setObjectName(f"guideImage{position}")
            image_label.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(str(calibration_guide_asset_path(asset)))
            if pixmap.isNull():
                image_label.setText(f"Guide image unavailable: {asset}")
            else:
                image_label.setPixmap(pixmap.scaled(
                    min(680, self.width() - 64), 300,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation))
            content_layout.addWidget(image_label)
            details = QLabel(instructions)
            details.setWordWrap(True)
            content_layout.addWidget(details)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        self.tabs.addTab(scroll, "Pictures")


class SingleBoardCapture(QThread):
    preview = pyqtSignal(QImage)
    status = pyqtSignal(str)
    sample = pyqtSignal(object)
    capture_finished = pyqtSignal()

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
            if self.side == "driver":
                configure_video_capture(capture)
            else:
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
                    self.capture_finished.emit()
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
        # result_ready precedes QThread.finished. Keep every fit alive until
        # finished so closing the dialog cannot destroy a running QThread.
        self._fit_jobs = set()
        self.individual_frames = {"left": [], "right": []}
        self.individual_corners = {"left": [], "right": []}
        self.intrinsics = {"left": None, "right": None}
        self.pairs, self.corner_pairs = [], []
        self.calibration_result = self.report = self.session_dir = None
        self.saved_path = None
        self.native_sizes = {}
        self.setWindowTitle("Road cameras - guided calibration")
        size_calibration_dialog(self, 900, 680)
        outer = QVBoxLayout(self)
        body = QWidget()
        layout = QVBoxLayout(body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.intro = QLabel(
            f"Step 1 of 3: calibrate LEFT road camera {primary} without the dark filter.\n"
            f"Then calibrate RIGHT camera {secondary}, followed by the fixed stereo pair. "
            "Do not move either camera after the stereo stage. Use a flat board with a white border; "
            "10 x 7 squares means 9 x 6 INNER corners.")
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        board_warning = QLabel(
            "Glue the printed checkerboard to a stiff, flat board before capturing views.")
        board_warning.setObjectName("calibrationTip")
        board_warning.setWordWrap(True)
        layout.addWidget(board_warning)
        form = QFormLayout()
        self.columns, self.rows = QSpinBox(), QSpinBox()
        for spin, value in ((self.columns, 9), (self.rows, 6)):
            spin.setRange(3, 20)
            spin.setValue(value)
        self.square = QDoubleSpinBox()
        self.square.setRange(0.1, 20)
        self.square.setDecimals(3)
        self.square.setValue(2.0)
        self.square.setSuffix(" cm")
        form.addRow("Inner corner columns:", self.columns)
        form.addRow("Inner corner rows:", self.rows)
        form.addRow("Measured square side:", self.square)
        layout.addLayout(form)
        previews = QHBoxLayout()
        self.left = CalibrationPreview("LEFT feed")
        self.right = CalibrationPreview("RIGHT: starts in step 2")
        self.preview_captions = {}
        for side, index, label in (("left", primary, self.left), ("right", secondary, self.right)):
            column = QVBoxLayout()
            caption = QLabel(f"{side.upper()} camera {index}: waiting for native frame")
            caption.setWordWrap(True)
            caption.setFixedHeight(36)
            self.preview_captions[side] = caption
            column.addWidget(caption)
            column.addWidget(label, 1)
            previews.addLayout(column, 1)
        layout.addLayout(previews, 1)
        self.counter = QLabel(f"0 / {MIN_SAMPLES} minimum LEFT views")
        self.frame_comparison = QLabel("")
        self.frame_comparison.setWordWrap(True)
        self.frame_comparison.setObjectName("mutedText")
        self.fit_status = QLabel("Calibration stages not yet fitted")
        self.fit_status.setWordWrap(True)
        self.fit_status.setStyleSheet(
            "background:#172431; color:#b9c9d6; border-radius:5px; padding:7px;")
        self.message = QLabel(
            "Measure the printed square, check LEFT/RIGHT indices, then start LEFT calibration.")
        self.message.setWordWrap(True)
        layout.addWidget(self.counter)
        layout.addWidget(self.frame_comparison)
        layout.addWidget(self.fit_status)
        layout.addWidget(self.message)
        self.visual_guide = command_button("Visual calibration guide...", "help", role="guide")
        self.print_board = command_button("Print A4 chessboard...", "print")
        outer.addLayout(CalibrationActions(self.visual_guide, self.print_board, stretch=False))
        self.start = command_button("Start LEFT calibration", "play")
        self.take = command_button("Capture LEFT view", "camera")
        self.fit = command_button("Fit LEFT intrinsics", "fit")
        self.save = command_button("Save stereo profile", "save", role="accent")
        close = command_button("Close", "close")
        outer.addLayout(CalibrationActions(self.start, self.take, self.fit, self.save, close))
        self.take.setEnabled(False)
        self.fit.setEnabled(False)
        self.save.setEnabled(False)
        self.visual_guide.clicked.connect(self._open_visual_guide)
        self.print_board.clicked.connect(self._open_printable_board)
        self.start.clicked.connect(self._start)
        self.take.clicked.connect(self._request_capture)
        self.fit.clicked.connect(self._fit)
        self.save.clicked.connect(self._save)
        close.clicked.connect(self.reject)

    def _open_visual_guide(self):
        guide = CalibrationVisualGuideDialog(self)
        guide.exec_()

    def _open_printable_board(self):
        """Open the dimensioned PDF so the operator can print at actual size."""
        board = printable_chessboard_path()
        if not board.is_file():
            self.message.setText(
                f"Printable chessboard is missing: {board}. Reinstall or regenerate it.")
            return
        # Keep the calibration fields synchronized with the supplied pattern.
        if self.columns.isEnabled():
            self.columns.setValue(9)
            self.rows.setValue(6)
            self.square.setValue(2.0)
        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(board))):
            self.message.setText(
                "Opened the verified A4 landscape chessboard. Print at Actual size / "
                "100% with Fit-to-page disabled, then measure several squares with a ruler.")
        else:
            self.message.setText(
                f"Windows could not open {board}. Open it manually in a PDF viewer.")

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
        if any(job.isRunning() for job in self._fit_jobs):
            self.message.setText("Calibration is still fitting; wait for the result.")
            return
        if self.capture_worker is not None and self.capture_worker.isRunning():
            return
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
            worker, side = self.capture_worker, self.stage
            worker.preview.connect(lambda image, role=side, owner=worker:
                                   self._single_preview(image, role) if owner is self.capture_worker else None)
            worker.sample.connect(lambda payload, role=side, owner=worker:
                                  self._sample_single(payload, role) if owner is self.capture_worker else None)
        else:
            self.capture_worker = StereoBoardCapture(self.indices, self.pattern, self)
            worker = self.capture_worker
            worker.preview.connect(lambda left, right, owner=worker:
                                   self._preview(left, right) if owner is self.capture_worker else None)
            worker.sample.connect(lambda payload, owner=worker:
                                  self._sample(payload) if owner is self.capture_worker else None)
        worker, side = self.capture_worker, self.stage
        worker.status.connect(lambda message, owner=worker, role=side:
                              self.message.setText(message)
                              if owner is self.capture_worker and role == self.stage else None)
        worker.finished.connect(lambda owner=worker, role=side: self._capture_finished(owner, role))
        self.take.setEnabled(True)
        self.capture_worker.start()

    def _enable_stage_retry(self):
        self.start.setText(f"Capture more {self.stage.upper()} views")
        self.start.setEnabled(True)
        count = len(self.pairs) if self.stage == "stereo" else len(self.individual_frames[self.stage])
        self.fit.setEnabled(count >= MIN_SAMPLES)

    def _capture_finished(self, worker, side):
        if worker is not self.capture_worker or side != self.stage:
            return
        self.take.setEnabled(False)
        if self.fit_worker is None and not any(job.isRunning() for job in self._fit_jobs):
            self._enable_stage_retry()
            if not (self.pairs if side == "stereo" else self.individual_frames[side]):
                self.start.setText(f"Retry {side.upper()} camera connection")

    def _request_capture(self):
        if self.capture_worker is not None:
            self.capture_worker.capture_requested.set()

    def _show_native_preview(self, side, image):
        label = self.left if side == "left" else self.right
        label.set_image(image)
        size = (image.width(), image.height())
        index = self.indices[0 if side == "left" else 1]
        self.preview_captions[side].setText(f"{side.upper()} camera {index}: raw {size[0]}×{size[1]} px · full frame")
        if self.native_sizes.get(side) != size:
            self.native_sizes[side] = size
            self._update_frame_comparison()

    def _single_preview(self, image, side=None):
        side = side or self.stage
        if side not in ("left", "right") or side != self.stage:
            return  # A queued LEFT frame must never become a RIGHT preview.
        self._show_native_preview(side, image)

    def _preview(self, left, right):
        self._show_native_preview("left", left)
        self._show_native_preview("right", right)

    def _update_frame_comparison(self):
        sizes = {side: self.native_sizes.get(side) or (camera.image_size if camera else None)
                 for side, camera in self.intrinsics.items()}
        if not all(sizes.values()):
            self.frame_comparison.setText("Compare raw pixel dimensions after both cameras have supplied a frame. Previews show the full image, without optical correction or cropping.")
            return
        left, right = sizes["left"], sizes["right"]
        matched = left == right
        text = (f"Frame resolution {'MATCHED' if matched else 'MISMATCHED'}: "
                f"LEFT {left[0]}×{left[1]}, RIGHT {right[0]}×{right[1]}. ")
        if not matched:
            text += "Stop and use matching native modes; samples are not resized to hide a mismatch."
        else:
            text += "Equal pixel size does not establish equal optical field of view."
            if all(self.intrinsics.values()):
                focal = [self.intrinsics[side].focal_length_px for side in ("left", "right")]
                text += f" Fitted fx differs by {abs(focal[0] - focal[1]) / max(abs(focal[0]), 1e-9) * 100:.1f}% relative to LEFT; check the same stationary target and unchanged focus."
        self.frame_comparison.setText(text)

    def _sample_size_valid(self, side, frame):
        size = (frame.shape[1], frame.shape[0])
        frames = self.individual_frames[side]
        expected = (frames[0].shape[1], frames[0].shape[0]) if frames else None
        other = self.intrinsics["right" if side == "left" else "left"]
        if (expected and size != expected) or (other and size != other.image_size):
            self.message.setText(f"View not accepted: native {side.upper()} size {size} differs from the existing calibration samples. Restart with matching camera modes; no resizing is applied.")
            return False
        return True

    def _sample_single(self, payload, side=None):
        if self.fit_worker is not None or (side is not None and side != self.stage):
            return
        frame, corners = payload
        if not self._sample_size_valid(self.stage, frame):
            return
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
        if left.shape[:2] != right.shape[:2]:
            self.message.setText("Pair not accepted: LEFT and RIGHT native resolutions differ; use matching camera modes.")
            return
        for side, frame in (("left", left), ("right", right)):
            model = self.intrinsics[side]
            if model is not None and (frame.shape[1], frame.shape[0]) != model.image_size:
                self.message.setText("Pair not accepted: native frame size changed after individual calibration. Restart using the same camera modes; no scaling is applied.")
                return
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
        if any(job.isRunning() for job in self._fit_jobs):
            return
        if not self._stop_capture():
            return
        self.start.setEnabled(False)
        self.take.setEnabled(False)
        self.fit.setEnabled(False)
        self.save.setEnabled(False)
        self.calibration_result = self.report = None
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
        worker = self.fit_worker
        self._fit_jobs.add(worker)
        worker.finished.connect(lambda owner=worker: self._fit_jobs.discard(owner))
        self.fit_worker.start()

    def _fit_failed(self, message):
        self.fit_worker = None
        self.calibration_result = self.report = None
        self.save.setEnabled(False)
        self.fit_status.setText("FIT FAILED — no calibration was saved")
        self.fit_status.setStyleSheet(
            "background:#461f27; color:#ffb5bf; border:1px solid #a94756; "
            "border-radius:5px; padding:7px; font-weight:700;")
        self.message.setText(
            f"Fit failed: {message}. If any saved view used loose or curved paper, "
            "close this calibration and restart with a rigid flat board; adding more "
            "views does not remove the invalid ones.")
        self._enable_stage_retry()

    def _single_fit_done(self, result):
        completed = self.stage
        if (completed == "right" and self.intrinsics["left"] is not None
                and result.image_size != self.intrinsics["left"].image_size):
            self._fit_failed("LEFT/RIGHT native resolutions differ; repeat with matching camera modes")
            return
        try:
            save_single_calibration(
                result, f"stereo_sessions/{self.session_dir.name}/{completed}_intrinsic")
            report = {"stage": completed, "rms_px": float(result.rms_error),
                      "image_size": list(result.image_size), "samples": len(
                          self.individual_frames[completed])}
            (self.session_dir / f"{completed}_report.json").write_text(
                json.dumps(report, indent=2))
        except OSError as error:
            self._fit_failed(f"Cannot archive {completed} calibration: {error}")
            return
        self.intrinsics[completed] = result
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
            self._update_frame_comparison()
            self.fit_status.setText(
                "INDIVIDUAL CALIBRATIONS PASSED — stereo fitting still required")
            self.fit_status.setStyleSheet(
                "background:#3a3212; color:#ffe49a; border:1px solid #a98a2e; "
                "border-radius:5px; padding:7px; font-weight:700;")
        label = self.stage.upper()
        self.counter.setText(f"0 / {MIN_SAMPLES} minimum {label} "
                             + ("pairs" if self.stage == "stereo" else "views"))
        self.start.setText(f"Start {label} calibration")
        self.take.setText("Capture pair" if self.stage == "stereo" else f"Capture {label} view")
        self.fit.setText("Fit stereo geometry" if self.stage == "stereo" else f"Fit {label} intrinsics")
        self.start.setEnabled(True)
        self.message.setText(
            f"{completed.upper()} intrinsics passed. Continue to {label} calibration.")
        if completed == "left":
            next_step = (
                f"LEFT camera calibration passed at {result.rms_error:.3f} px.\n\n"
                f"Next: calibrate RIGHT camera {self.indices[1]} using the same rigid, "
                "flat board. Compare native pixel dimensions; compare apparent zoom only "
                "with the same stationary target and unchanged focus.")
        else:
            next_step = (
                f"RIGHT camera calibration passed at {result.rms_error:.3f} px.\n\n"
                "Next: rigidly fix both cameras in their final LEFT/RIGHT positions. "
                "Do not move or refocus them, then capture paired stereo views with the "
                "flat board visible in both feeds.")
        QMessageBox.information(
            self,
            f"{completed.upper()} intrinsic calibration passed",
            next_step,
        )

    def _fit_done(self, result, report):
        self.fit_worker = None
        try:
            (self.session_dir / "report.json").write_text(json.dumps(report, indent=2))
        except OSError as error:
            self._fit_failed(f"Cannot save fit report: {error}")
            return
        self.calibration_result, self.report = result, report
        self._enable_stage_retry()
        self.message.setText(
            f"Stereo RMS {report['stereo_rms_px']:.3f} px; "
            f"row error p95 {report['fit_rectified_row_p95_px']:.3f} px; "
            f"baseline {report['baseline_cm']:.2f} cm. "
            + ("Check baseline against a ruler, then save. Apply filters only after this; "
               "the filtered setup must pass a geometric verification before measurements."
               if report["passed"] else
               "Not accepted. Check order, square size, focus, rigidity and pose variety."))
        self.save.setEnabled(report["passed"])
        if report["passed"]:
            self.fit_status.setText(
                "STEREO FIT PASSED — NOT SAVED YET. Verify the measured baseline, "
                "then click Save stereo profile.")
            self.fit_status.setStyleSheet(
                "background:#153a28; color:#c9ffda; border:1px solid #52d273; "
                "border-radius:5px; padding:7px; font-weight:700;")
        else:
            reasons = []
            if report["stereo_rms_px"] > report["max_rms_px"]:
                reasons.append("stereo RMS above limit")
            if report["fit_rectified_row_p95_px"] > report["max_row_p95_px"]:
                reasons.append("rectified row error above limit")
            if result.P2[0, 3] >= 0:
                reasons.append("LEFT/RIGHT camera order appears reversed")
            detail = ", ".join(reasons) or "fit-quality gate failed"
            self.fit_status.setText(
                f"STEREO FIT NOT ACCEPTED — {detail}. No profile was saved.")
            self.fit_status.setStyleSheet(
                "background:#461f27; color:#ffb5bf; border:1px solid #a94756; "
                "border-radius:5px; padding:7px; font-weight:700;")

    def _save(self):
        if (not self.calibration_result or not self.report
                or not self.report["passed"]):
            return
        try:
            name = stereo_profile_name(*self.indices)
            archive_name = f"stereo_sessions/{self.session_dir.name}/accepted"
            save_stereo_calibration(self.calibration_result, archive_name)
            self.saved_path = save_stereo_calibration(self.calibration_result, name)
            self.message.setText(
                f"CALIBRATION COMPLETE. Saved {self.saved_path}. Apply the dark filters "
                "without moving cameras, then perform the post-filter verification before "
                "collecting measurements.")
            self.fit_status.setText(
                "CALIBRATION COMPLETE — STEREO PROFILE SAVED")
            self.save.setEnabled(False)
            QMessageBox.information(
                self,
                "Stereo calibration complete — profile saved",
                "SUCCESS: The road stereo profile was saved successfully.\n\n"
                "Do not move or refocus either camera. Apply the dark filters, close this "
                "message, then use Standby to verify both feeds before measurements.",
            )
            self.accept()
        except Exception as error:
            self.message.setText(f"Save failed: {error}")

    def done(self, code):
        if (any(job.isRunning() for job in self._fit_jobs)
                or (self.fit_worker and self.fit_worker.isRunning())):
            self.message.setText("Calibration is still fitting; close after it finishes.")
            return
        if self._stop_capture():
            super().done(code)

    def closeEvent(self, event):
        event.ignore()
        self.reject()
