"""Stereo headlight detection using two USB webcams.

Detects the brightest spot (headlight) in two synchronized camera frames
and triangulates its 3D position in real-time.
"""

from __future__ import annotations

import sys
import time
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from glare_tracker.calibration import StereoCalibrationResult, load_stereo_calibration


def detect_bright_spot(
    frame: np.ndarray, thresh_val: int = 240, min_area: float = 5.0, max_area: float = 10000.0,
) -> Optional[tuple[float, float]]:
    """Detect the brightest light source in a frame using intensity-weighted centroid.

    Returns (cx, cy) tuple or None.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Pick the largest contour (primary light core)
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area < min_area or area > max_area:
        return None

    # Intensity-weighted centroid for sub-pixel accuracy
    x, y, w, h = cv2.boundingRect(c)
    roi_gray = gray[y:y+h, x:x+w].astype(np.float64)
    roi_thresh = thresh[y:y+h, x:x+w] > 0

    weights = roi_gray * roi_thresh
    total_weight = np.sum(weights)

    if total_weight == 0:
        M = cv2.moments(c)
        if M["m00"] == 0: return None
        return (float(M["m10"] / M["m00"]), float(M["m01"] / M["m00"]))

    y_grid, x_grid = np.indices(weights.shape)
    cx = x + (np.sum(x_grid * weights) / total_weight)
    cy = y + (np.sum(y_grid * weights) / total_weight)

    return (float(cx), float(cy))


class MonocularHeadlightDetectorThread(QThread):
    """Detect a headlight with one outward-facing camera.

    A single camera cannot measure depth on its own, so ``depth_cm`` is a
    user-provided distance.  The image point is projected onto that depth
    plane with the camera mounted at the windshield's top-centre.
    """

    frame_ready = pyqtSignal(QImage)
    headlight_detected = pyqtSignal(float, float, float)
    headlight_lost = pyqtSignal()
    camera_status = pyqtSignal(str, bool)

    def __init__(
        self, camera_index: int = 1, depth_cm: float = 120.0,
        windshield_h_cm: float = 19.5, hfov_deg: float = 70.0,
        brightness_threshold: int = 240, parent=None,
    ):
        super().__init__(parent)
        self.camera_index = camera_index
        self.depth_cm = depth_cm
        self.windshield_h_cm = windshield_h_cm
        self.hfov_deg = hfov_deg
        self.brightness_threshold = brightness_threshold
        self._running = False

    def update_projection(
        self, depth_cm: float, windshield_h_cm: float, hfov_deg: float,
        brightness_threshold: int,
    ):
        self.depth_cm = depth_cm
        self.windshield_h_cm = windshield_h_cm
        self.hfov_deg = hfov_deg
        self.brightness_threshold = brightness_threshold

    def stop(self):
        self._running = False
        if self.isRunning():
            self.wait(5000)

    def run(self):
        self._running = True
        cap = None
        try:
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                self.camera_status.emit(
                    f"Camera {self.camera_index} not detected", False)
                self.headlight_lost.emit()
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_EXPOSURE, -8)
            self.camera_status.emit(
                f"Camera {self.camera_index} connected (single)", True)

            while self._running:
                ok, frame = cap.read()
                if not ok:
                    self.camera_status.emit(
                        f"Camera {self.camera_index} frame unavailable", False)
                    self.msleep(30)
                    continue

                point = detect_bright_spot(
                    frame, thresh_val=int(self.brightness_threshold))
                if point is None:
                    self.headlight_lost.emit()
                else:
                    u, v = point
                    h, w = frame.shape[:2]
                    depth = max(1.0, float(self.depth_cm))
                    hfov = np.deg2rad(np.clip(self.hfov_deg, 10.0, 170.0))
                    fx = (w / 2.0) / np.tan(hfov / 2.0)
                    fy = fx

                    # Camera origin: top-centre of windshield (0, 0, H).
                    gt_x = (u - w / 2.0) * depth / fx
                    gt_y = depth
                    gt_z = self.windshield_h_cm - (v - h / 2.0) * depth / fy
                    self.headlight_detected.emit(gt_x, gt_y, gt_z)
                    cv2.circle(frame, (int(u), int(v)), 10, (0, 255, 0), 2)
                    cv2.putText(
                        frame, f"X:{gt_x:.1f} Y:{gt_y:.1f} Z:{gt_z:.1f} cm",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (0, 255, 0), 2,
                    )

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                image = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
                self.frame_ready.emit(image)
        except Exception as error:
            print(f"Single-camera headlight tracking stopped: {error}", file=sys.stderr)
            self.camera_status.emit(f"Camera error: {error}", False)
            self.headlight_lost.emit()
        finally:
            if cap is not None:
                cap.release()
            self._running = False


class HeadlightDetectorThread(QThread):
    """Captures from a stereo pair of webcams and triangulates the light source.

    Signals
    -------
    frame_ready(QImage)
        Side-by-side composite frame for UI monitoring.
    headlight_detected(float, float, float)
        Triangulated 3D position (X, Y, Z) in cm.
    headlight_lost()
        Emitted when the light is not visible in both cameras.
    """

    frame_ready = pyqtSignal(QImage)
    headlight_detected = pyqtSignal(float, float, float)
    headlight_lost = pyqtSignal()
    camera_status = pyqtSignal(str, bool)

    def __init__(
        self, cam1_idx: int = 1, cam2_idx: int = 2,
        camera_height_cm: float = 19.5, brightness_threshold: int = 240,
        parent=None,
    ):
        super().__init__(parent)
        self.cam1_idx = cam1_idx
        self.cam2_idx = cam2_idx
        self.camera_height_cm = camera_height_cm
        self.brightness_threshold = brightness_threshold
        self._running = False
        self._calib: Optional[StereoCalibrationResult] = None

        try:
            self._calib = load_stereo_calibration()
        except Exception:
            pass

    def stop(self):
        self._running = False
        if self.isRunning():
            self.wait(5000)

    def update_detection_threshold(self, value: int):
        self.brightness_threshold = value

    def run(self):  # noqa: C901
        self._running = True
        cap1, cap2 = None, None

        try:
            cap1 = cv2.VideoCapture(self.cam1_idx, cv2.CAP_DSHOW)
            cap2 = cv2.VideoCapture(self.cam2_idx, cv2.CAP_DSHOW)

            if not cap1.isOpened() or not cap2.isOpened():
                missing = []
                if not cap1.isOpened():
                    missing.append(str(self.cam1_idx))
                if not cap2.isOpened():
                    missing.append(str(self.cam2_idx))
                self.camera_status.emit(
                    f"Camera(s) {', '.join(missing)} not detected", False)
                self.headlight_lost.emit()
                return

            self.camera_status.emit(
                f"Cameras {self.cam1_idx} + {self.cam2_idx} connected (stereo)", True)

            for cap in (cap1, cap2):
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)
                # Lock exposure to dark mode to isolate the bright light
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                cap.set(cv2.CAP_PROP_EXPOSURE, -8)

            while self._running:
                # Hardware-level near-simultaneous grab
                if not (cap1.grab() and cap2.grab()):
                    self.msleep(10)
                    continue

                ret1, frame1 = cap1.retrieve()
                ret2, frame2 = cap2.retrieve()
                if not (ret1 and ret2):
                    continue

                threshold = int(self.brightness_threshold)
                pt1 = detect_bright_spot(frame1, thresh_val=threshold)
                pt2 = detect_bright_spot(frame2, thresh_val=threshold)

                detected = False

                if pt1 is not None and pt2 is not None:
                    # Draw detection overlays
                    cv2.circle(frame1, (int(pt1[0]), int(pt1[1])), 10, (0, 255, 0), 2)
                    cv2.circle(frame2, (int(pt2[0]), int(pt2[1])), 10, (0, 255, 0), 2)

                    if self._calib is not None:
                        # ── CALIBRATED STEREO ──
                        p1_in = np.array([[[pt1[0], pt1[1]]]], dtype=np.float32)
                        p2_in = np.array([[[pt2[0], pt2[1]]]], dtype=np.float32)

                        pt1_rect = cv2.undistortPoints(
                            p1_in, self._calib.cam1.camera_matrix, self._calib.cam1.dist_coeffs,
                            R=self._calib.R1, P=self._calib.P1,
                        )
                        pt2_rect = cv2.undistortPoints(
                            p2_in, self._calib.cam2.camera_matrix, self._calib.cam2.dist_coeffs,
                            R=self._calib.R2, P=self._calib.P2,
                        )

                        x1_r, y1_r = pt1_rect[0, 0]
                        x2_r, y2_r = pt2_rect[0, 0]

                        # Epipolar verification (should be on similar horizontal scanline)
                        if abs(y1_r - y2_r) < 20.0:  # generous tolerance for physical flex
                            disparity = x1_r - x2_r
                            if disparity > 0.1:
                                f = self._calib.P1[0, 0]
                                cx = self._calib.P1[0, 2]
                                cy = self._calib.P1[1, 2]
                                Z_cm = (f * self._calib.baseline_cm) / disparity
                                X_cm = (x1_r - cx) * Z_cm / f
                                Y_cm = (y1_r - cy) * Z_cm / f
                                
                                # Remap from stereo camera coordinate space to global space
                                # Z is depth, Y is down in camera space.
                                # GlareTracker global space: X is lateral, Y is depth (positive in front), Z is up.
                                # Stereo rig origin is midway between cameras.
                                gt_x = X_cm - self._calib.baseline_cm / 2.0
                                gt_y = Z_cm
                                gt_z = -Y_cm + self.camera_height_cm

                                self.headlight_detected.emit(gt_x, gt_y, gt_z)
                                detected = True
                    else:
                        # ── UNCALIBRATED FALLBACK ──
                        # Hardcoded fallback assuming 25cm baseline, ~900px focal length at 720p
                        f = 900.0
                        baseline_cm = 25.0
                        cx = frame1.shape[1] / 2
                        cy = frame1.shape[0] / 2
                        
                        x1, y1 = pt1
                        x2, y2 = pt2
                        
                        # Very naive uncalibrated triangulation
                        disparity = x1 - x2
                        if disparity > 0.1:
                            Z_cm = (f * baseline_cm) / disparity
                            X_cm = (x1 - cx) * Z_cm / f
                            Y_cm = (y1 - cy) * Z_cm / f
                            
                            # Fallback coordinates are also centred on the rig.
                            gt_x = X_cm - baseline_cm / 2.0
                            gt_y = Z_cm
                            gt_z = -Y_cm + self.camera_height_cm
                            
                            self.headlight_detected.emit(gt_x, gt_y, gt_z)
                            detected = True

                if not detected:
                    self.headlight_lost.emit()

                # Compose side-by-side view for UI
                h1, w1 = frame1.shape[:2]
                h2, w2 = frame2.shape[:2]
                target_w = 320
                target_h = int(h1 * (target_w / w1))
                
                f1_small = cv2.resize(frame1, (target_w, target_h))
                f2_small = cv2.resize(frame2, (target_w, target_h))
                
                composite = np.hstack((f1_small, f2_small))
                composite_rgb = cv2.cvtColor(composite, cv2.COLOR_BGR2RGB)
                
                ch, cw = composite_rgb.shape[:2]
                q_img = QImage(composite_rgb.data, cw, ch, cw * 3, QImage.Format_RGB888).copy()
                self.frame_ready.emit(q_img)

        except Exception as error:
            print(f"Stereo headlight tracking stopped: {error}", file=sys.stderr)
            self.camera_status.emit(f"Stereo camera error: {error}", False)
            self.headlight_lost.emit()
        finally:
            if cap1 is not None: cap1.release()
            if cap2 is not None: cap2.release()
            self._running = False
