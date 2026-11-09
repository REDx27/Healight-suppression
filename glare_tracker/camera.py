"""Background camera capture with MediaPipe eye tracking.

Runs OpenCV + MediaPipe FaceMesh in a ``QThread`` so the GUI never blocks.
Supports both uncalibrated (linear mapping) and calibrated (intrinsic + PnP)
eye tracking modes.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from glare_tracker.calibration import CalibrationResult, load_single_calibration
from glare_tracker.capture import configure_video_capture, open_video_capture
from glare_tracker.config import TrackingConfig
from glare_tracker.drowsiness import DrowsinessDetector, DrowsinessSettings
from glare_tracker.geometry import (
    estimate_ipd_depth,
    pixel_to_cm,
    pixel_to_cm_calibrated,
)


# ── Head pose model points (anthropometric, in cm) ──────────────────

# 6 stable facial landmarks for solvePnP (centred at nose tip = origin)
_HEAD_MODEL_POINTS_CM = np.array([
    (0.0,    0.0,    0.0),     # Nose tip           (lm 1)
    (0.0,   -6.5,   -2.5),    # Chin                (lm 152)
    (-4.5,   3.5,   -3.5),    # Right eye outer      (lm 33)
    (4.5,    3.5,   -3.5),    # Left eye outer       (lm 263)
    (-3.0,  -3.0,   -3.0),    # Right mouth corner   (lm 61)
    (3.0,   -3.0,   -3.0),    # Left mouth corner    (lm 291)
], dtype=np.float64)

_HEAD_LANDMARK_INDICES = [1, 152, 33, 263, 61, 291]


class VideoCaptureThread(QThread):
    """Captures webcam frames, detects iris positions, and emits results.

    Signals
    -------
    frame_ready(QImage)
        Camera frame (RGB) with iris overlay drawn on it.
    eye_detected(float, float, float)
        Eye midpoint in centimetres ``(x, y, z)``.
    eyes_detected(float, float, float, float, float, float)
        Both eyes individually: ``(left_x, left_y, left_z, right_x, right_y, right_z)``.
    eye_lost()
        Emitted when no face / iris is detected in the current frame.
    depth_updated(float)
        Current estimated depth in cm (from IPD).
    head_pose_updated(float, float, float)
        Head rotation angles: ``(pitch, yaw, roll)`` in degrees.
    """

    frame_ready = pyqtSignal(QImage)
    eye_detected = pyqtSignal(float, float, float)
    eyes_detected = pyqtSignal(float, float, float, float, float, float)
    eye_lost = pyqtSignal()
    depth_updated = pyqtSignal(float)
    head_pose_updated = pyqtSignal(float, float, float)
    eye_pixels_detected = pyqtSignal(float, float, float, float, int, int)
    camera_status = pyqtSignal(str, bool)
    pipeline_timing = pyqtSignal(object)
    drowsiness_updated = pyqtSignal(object)

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self._running = False
        self._config = TrackingConfig()
        self._calibration: Optional[CalibrationResult] = None
        self._drowsiness = DrowsinessDetector()

        # Try to load existing calibration on init
        self._try_load_calibration()

    # ── public API ──────────────────────────────────────────────────

    def update_config(self, config: TrackingConfig):
        """Replace the current tracking configuration (thread-safe for primitives)."""
        self._config = config

    def set_calibration(self, calib: Optional[CalibrationResult]):
        """Set or clear camera calibration data."""
        self._calibration = calib

    def update_drowsiness_settings(self, settings: DrowsinessSettings):
        """Replace experimental driver-monitoring thresholds."""
        self._drowsiness.update_settings(settings)
        if not self._drowsiness.settings.enabled:
            self.drowsiness_updated.emit(self._drowsiness.unavailable().as_dict())

    def stop(self):
        """Request the thread to stop and wait for it to finish."""
        self._running = False
        if self.isRunning():
            self.wait(5000)

    # ── helpers ─────────────────────────────────────────────────────

    def _try_load_calibration(self):
        """Attempt to load saved calibration data for the driver camera."""
        try:
            self._calibration = load_single_calibration("driver_cam")
        except Exception:
            self._calibration = None

    @staticmethod
    def _face_landmarker_model_path() -> str:
        """Return the bundled Tasks API face-landmarker model path."""
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "assets", "face_landmarker.task")

    @classmethod
    def _create_face_tracker(cls):
        """Create a face tracker compatible with legacy and current MediaPipe."""
        if hasattr(mp, "solutions"):
            tracker = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            return tracker, False

        model_path = cls._face_landmarker_model_path()
        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"MediaPipe face-landmarker model not found: {model_path}"
            )
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        tracker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        return tracker, True

    def _estimate_head_pose(
        self, landmarks, img_w: int, img_h: int, camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
    ) -> Optional[tuple]:
        """Compute head pose using solvePnP.

        Returns (pitch, yaw, roll, tvec) or None.
        """
        image_points = np.array([
            [landmarks[idx].x * img_w, landmarks[idx].y * img_h]
            for idx in _HEAD_LANDMARK_INDICES
        ], dtype=np.float64)

        success, rvec, tvec = cv2.solvePnP(
            _HEAD_MODEL_POINTS_CM, image_points,
            camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            return None

        R, _ = cv2.Rodrigues(rvec)
        proj = np.hstack((R, tvec))
        _, _, _, _, _, _, euler = cv2.decomposeProjectionMatrix(proj)
        pitch, yaw, roll = euler.flatten()[:3]

        return (float(pitch), float(yaw), float(roll), tvec.flatten())

    # ── thread body ─────────────────────────────────────────────────

    def run(self):  # noqa: C901
        self._running = True
        cap = None
        face_mesh = None

        try:
            cap, backend_name = open_video_capture(self.camera_index)
            if cap is None:
                self.camera_status.emit(
                    f"Camera {self.camera_index} not detected", False)
                self.eye_lost.emit()
                self.drowsiness_updated.emit(
                    self._drowsiness.unavailable().as_dict())
                return

            width, height, _ = configure_video_capture(cap)
            self.camera_status.emit(
                f"Camera {self.camera_index} connected via {backend_name} "
                f"({width}x{height})", True)

            face_mesh, uses_tasks_api = self._create_face_tracker()
            frame_number = 0

            while self._running:
                capture_started_ns = time.monotonic_ns()
                ret, frame = cap.read()
                if not ret:
                    self.msleep(10)
                    continue
                capture_complete_ns = time.monotonic_ns()
                frame_number += 1

                frame = cv2.flip(frame, 1)  # mirror for natural feel
                h, w, _ = frame.shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if uses_tasks_api:
                    mp_image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=np.ascontiguousarray(rgb),
                    )
                    timestamp_ms = int(time.monotonic() * 1000)
                    results = face_mesh.detect_for_video(mp_image, timestamp_ms)
                    faces = results.face_landmarks
                else:
                    results = face_mesh.process(rgb)
                    faces = [face.landmark for face in results.multi_face_landmarks or []]
                detection_complete_ns = time.monotonic_ns()
                self.pipeline_timing.emit({
                    "stream": "driver",
                    "frame_index": frame_number,
                    "capture_started_ns": capture_started_ns,
                    "capture_complete_ns": capture_complete_ns,
                    "detection_complete_ns": detection_complete_ns,
                    "observation_valid": bool(faces),
                })

                if faces:
                    lm = faces[0]
                    config = self._config
                    calib = self._calibration if config.use_calibration else None

                    if self._drowsiness.settings.enabled:
                        metrics = self._drowsiness.update(lm, w, h)
                        self.drowsiness_updated.emit(metrics.as_dict())

                    # MediaPipe iris-centre landmarks: left 468, right 473
                    left_iris = lm[468]
                    right_iris = lm[473]

                    # Pixel positions of each iris
                    lx_px = left_iris.x * w
                    ly_px = left_iris.y * h
                    rx_px = right_iris.x * w
                    ry_px = right_iris.y * h

                    # Midpoint (used for backward compat)
                    eye_x_px = (lx_px + rx_px) / 2
                    eye_y_px = (ly_px + ry_px) / 2
                    self.eye_pixels_detected.emit(
                        lx_px, ly_px, rx_px, ry_px, w, h)

                    # Draw overlays on the RGB frame
                    cv2.circle(rgb, (int(eye_x_px), int(eye_y_px)), 6, (255, 50, 50), -1)
                    cv2.circle(rgb, (int(eye_x_px), int(eye_y_px)), 10, (255, 100, 100), 2)
                    cv2.circle(rgb, (int(lx_px), int(ly_px)), 3, (100, 200, 255), -1)
                    cv2.circle(rgb, (int(rx_px), int(ry_px)), 3, (100, 200, 255), -1)

                    if calib is not None:
                        # ── CALIBRATED MODE ──
                        mtx = calib.camera_matrix
                        dist = calib.dist_coeffs
                        fx = calib.focal_length_px

                        # Head pose estimation
                        yaw_deg = 0.0
                        pose = self._estimate_head_pose(lm, w, h, mtx, dist)
                        if pose is not None:
                            pitch, yaw_deg, roll, tvec = pose
                            self.head_pose_updated.emit(pitch, yaw_deg, roll)

                        # IPD-based depth estimation
                        depth_cm = estimate_ipd_depth(
                            (lx_px, ly_px), (rx_px, ry_px),
                            fx, config.ipd_cm, yaw_deg,
                        )
                        self.depth_updated.emit(depth_cm)

                        # Calibrated unprojection for each eye
                        left_cm = pixel_to_cm_calibrated(
                            lx_px, ly_px, depth_cm,
                            mtx, dist, config.screen_h_cm,
                        )
                        right_cm = pixel_to_cm_calibrated(
                            rx_px, ry_px, depth_cm,
                            mtx, dist, config.screen_h_cm,
                        )
                        mid_cm = (
                            (left_cm[0] + right_cm[0]) / 2,
                            (left_cm[1] + right_cm[1]) / 2,
                            (left_cm[2] + right_cm[2]) / 2,
                        )

                        # Draw depth on frame
                        cv2.putText(
                            rgb, f"D:{depth_cm:.0f}cm Y:{yaw_deg:.0f}deg",
                            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                            (100, 255, 100), 1,
                        )

                        self.eye_detected.emit(*mid_cm)
                        self.eyes_detected.emit(
                            *left_cm, *right_cm,
                        )
                    else:
                        # ── UNCALIBRATED MODE (fallback) ──
                        left_cm = pixel_to_cm(
                            lx_px, ly_px, w, h,
                            config.screen_w_cm, config.screen_h_cm,
                            config.eye_dist_cm,
                        )
                        right_cm = pixel_to_cm(
                            rx_px, ry_px, w, h,
                            config.screen_w_cm, config.screen_h_cm,
                            config.eye_dist_cm,
                        )
                        mid_cm = tuple(
                            (left + right) / 2.0
                            for left, right in zip(left_cm, right_cm)
                        )
                        self.eye_detected.emit(*mid_cm)
                        self.eyes_detected.emit(*left_cm, *right_cm)
                else:
                    self.eye_lost.emit()
                    if self._drowsiness.settings.enabled:
                        self.drowsiness_updated.emit(
                            self._drowsiness.unavailable().as_dict())

                # .copy() so Qt owns the buffer
                bytes_per_line = 3 * w
                q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.frame_ready.emit(q_img)

        except Exception as error:
            print(f"Camera tracking stopped: {error}", file=sys.stderr)
            self.camera_status.emit(f"Driver camera error: {error}", False)
            self.eye_lost.emit()
            self.drowsiness_updated.emit(
                self._drowsiness.unavailable().as_dict())
        finally:
            if face_mesh is not None:
                face_mesh.close()
            if cap is not None:
                cap.release()
            self._running = False
