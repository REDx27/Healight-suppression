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
from glare_tracker.capture import configure_video_capture, open_video_capture


class TemporalPointFilter:
    """Smooth a tracked point and bridge a few dropped detections.

    Camera exposure changes and threshold noise can make an otherwise steady
    light disappear for one or two frames.  Keeping the last position briefly
    prevents that normal noise from flickering the UI and windshield marker.
    """

    def __init__(
        self, alpha: float = 0.32, hold_frames: int = 5,
        max_step: Optional[float] = None,
    ):
        self.alpha = float(np.clip(alpha, 0.01, 1.0))
        self.hold_frames = max(0, int(hold_frames))
        self.max_step = max_step
        self._point: Optional[np.ndarray] = None
        self._missing_frames = 0

    @property
    def point(self) -> Optional[tuple[float, ...]]:
        if self._point is None:
            return None
        return tuple(float(value) for value in self._point)

    def update(self, measurement) -> Optional[tuple[float, ...]]:
        if measurement is None:
            self._missing_frames += 1
            if self._point is not None and self._missing_frames <= self.hold_frames:
                return self.point
            self._point = None
            return None

        measured = np.asarray(measurement, dtype=np.float64)
        self._missing_frames = 0
        if self._point is None or self._point.shape != measured.shape:
            self._point = measured
            return self.point

        delta = measured - self._point
        if self.max_step is not None:
            distance = float(np.linalg.norm(delta))
            if distance > self.max_step > 0:
                delta *= self.max_step / distance
        self._point = self._point + self.alpha * delta
        return self.point


def detect_bright_spot(
    frame: np.ndarray, thresh_val: int = 210, min_area: float = 5.0,
    max_area: float = 10000.0,
    previous_point: Optional[tuple[float, float]] = None,
) -> Optional[tuple[float, float]]:
    """Detect a compact light source using contrast and weighted centroid.

    The threshold is combined with the frame's background level so exposure
    changes do not turn ordinary bright surfaces into headlights.  When more
    than one candidate exists, proximity to the previous result discourages
    the detector from jumping between sources.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    background = float(np.percentile(blurred, 90.0))
    peak = float(np.max(blurred))
    requested_threshold = float(np.clip(thresh_val, 0, 255))
    # Treat the configured value as the preferred threshold, then relax it
    # when a camera maps its brightness range below that value.  Contrast to
    # the current frame background remains mandatory, preventing this from
    # simply selecting the brightest ordinary object in the scene.
    threshold = max(background + 18.0, min(requested_threshold, peak - 12.0))
    if peak < 40.0 or peak - background < 24.0 or threshold >= 255.0:
        return None

    _, thresh = cv2.threshold(
        blurred, min(254.0, threshold), 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    candidates = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area or area > max_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if h == 0 or not 0.2 <= (w / h) <= 5.0:
            continue
        roi_gray = gray[y:y+h, x:x+w].astype(np.float64)
        roi_mask = thresh[y:y+h, x:x+w] > 0
        weights = roi_gray * roi_mask
        total_weight = float(np.sum(weights))
        if total_weight <= 0:
            continue

        y_grid, x_grid = np.indices(weights.shape)
        cx = float(x + np.sum(x_grid * weights) / total_weight)
        cy = float(y + np.sum(y_grid * weights) / total_weight)
        mean_brightness = float(np.mean(roi_gray[roi_mask]))
        local_peak = float(np.max(roi_gray))
        perimeter = float(cv2.arcLength(contour, True))
        compactness = (4.0 * np.pi * area / (perimeter * perimeter)
                       if perimeter > 0 else 0.0)

        score = local_peak + 0.35 * mean_brightness + 12.0 * compactness
        score += min(18.0, 3.0 * np.log1p(area))
        if previous_point is not None:
            distance = float(np.hypot(cx - previous_point[0], cy - previous_point[1]))
            score -= min(55.0, distance * 0.08)
        candidates.append((score, cx, cy))

    if not candidates:
        return None
    _, cx, cy = max(candidates, key=lambda candidate: candidate[0])
    return (cx, cy)


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
        brightness_threshold: int = 210, parent=None,
    ):
        super().__init__(parent)
        self.camera_index = camera_index
        self.depth_cm = depth_cm
        self.windshield_h_cm = windshield_h_cm
        self.hfov_deg = hfov_deg
        self.brightness_threshold = brightness_threshold
        self._running = False
        self._point_filter = TemporalPointFilter(
            alpha=0.32, hold_frames=5, max_step=180.0)

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
            cap, backend_name = open_video_capture(self.camera_index)
            if cap is None:
                self.camera_status.emit(
                    f"Camera {self.camera_index} not detected", False)
                self.headlight_lost.emit()
                return

            # Many inexpensive USB cameras fall back to a very slow raw-video
            # mode at 720p.  MJPEG 640x480 is widely supported and keeps the
            # monocular tracker responsive while retaining enough resolution
            # for a bright-source centroid.
            width, height, _ = configure_video_capture(cap)
            self.camera_status.emit(
                f"Camera {self.camera_index} connected via {backend_name} "
                f"({width}x{height}, single)", True)

            lost_announced = False
            frame_number = 0
            brightness_90 = 0.0
            measured_fps = 0.0
            fps_frames = 0
            fps_started = time.monotonic()
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    self.camera_status.emit(
                        f"Camera {self.camera_index} frame unavailable", False)
                    self.msleep(30)
                    continue

                frame_number += 1
                # Observe exposure without forcing vendor-specific controls.
                # Most inexpensive webcams are more reliable in their default
                # auto-exposure mode; detection adapts in software instead.
                if frame_number % 8 == 0:
                    sample = cv2.resize(frame, (160, 120))
                    sample_gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
                    brightness_90 = float(np.percentile(sample_gray, 90.0))

                fps_frames += 1
                fps_elapsed = time.monotonic() - fps_started
                if fps_elapsed >= 1.0:
                    measured_fps = fps_frames / fps_elapsed
                    fps_frames = 0
                    fps_started = time.monotonic()

                raw_point = detect_bright_spot(
                    frame,
                    thresh_val=int(self.brightness_threshold),
                    previous_point=self._point_filter.point,
                )
                point = self._point_filter.update(raw_point)
                if point is None:
                    if not lost_announced:
                        self.headlight_lost.emit()
                        lost_announced = True
                else:
                    lost_announced = False
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

                if brightness_90 > 245.0:
                    cv2.putText(
                        frame, "OVEREXPOSED - move light farther away",
                        (10, frame.shape[0] - 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 80, 255), 2,
                    )

                cv2.putText(
                    frame,
                    f"{frame.shape[1]}x{frame.shape[0]}  {measured_fps:.1f} FPS  "
                    f"T:{int(self.brightness_threshold)}",
                    (10, frame.shape[0] - 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 220, 80), 1,
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
        camera_height_cm: float = 19.5, brightness_threshold: int = 210,
        parent=None,
    ):
        super().__init__(parent)
        self.cam1_idx = cam1_idx
        self.cam2_idx = cam2_idx
        self.camera_height_cm = camera_height_cm
        self.brightness_threshold = brightness_threshold
        self._running = False
        self._point_filter_1 = TemporalPointFilter(
            alpha=0.32, hold_frames=4, max_step=180.0)
        self._point_filter_2 = TemporalPointFilter(
            alpha=0.32, hold_frames=4, max_step=180.0)
        self._position_filter = TemporalPointFilter(
            alpha=0.24, hold_frames=4)
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
            cap1, backend1 = open_video_capture(self.cam1_idx)
            cap2, backend2 = open_video_capture(self.cam2_idx)

            if cap1 is None or cap2 is None:
                missing = []
                if cap1 is None:
                    missing.append(str(self.cam1_idx))
                if cap2 is None:
                    missing.append(str(self.cam2_idx))
                self.camera_status.emit(
                    f"Camera(s) {', '.join(missing)} not detected", False)
                self.headlight_lost.emit()
                return

            self.camera_status.emit(
                f"Cameras {self.cam1_idx} ({backend1}) + "
                f"{self.cam2_idx} ({backend2}) connected (stereo)", True)

            for cap in (cap1, cap2):
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)
                # Lock exposure to dark mode to isolate the bright light
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                cap.set(cv2.CAP_PROP_EXPOSURE, -6)

            lost_announced = False
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
                raw_pt1 = detect_bright_spot(
                    frame1, thresh_val=threshold,
                    previous_point=self._point_filter_1.point)
                raw_pt2 = detect_bright_spot(
                    frame2, thresh_val=threshold,
                    previous_point=self._point_filter_2.point)
                pt1 = self._point_filter_1.update(raw_pt1)
                pt2 = self._point_filter_2.update(raw_pt2)

                position = None

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

                                position = (gt_x, gt_y, gt_z)
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
                            
                            position = (gt_x, gt_y, gt_z)

                stable_position = self._position_filter.update(position)
                if stable_position is None:
                    if not lost_announced:
                        self.headlight_lost.emit()
                        lost_announced = True
                else:
                    lost_announced = False
                    self.headlight_detected.emit(*stable_position)

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
