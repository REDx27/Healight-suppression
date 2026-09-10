"""Background camera capture with MediaPipe eye tracking.

Runs OpenCV + MediaPipe FaceMesh in a ``QThread`` so the GUI never blocks.
"""

import sys

import cv2
import mediapipe as mp
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from glare_tracker.config import TrackingConfig
from glare_tracker.geometry import pixel_to_cm


class VideoCaptureThread(QThread):
    """Captures webcam frames, detects iris positions, and emits results.

    Signals
    -------
    frame_ready(QImage)
        Camera frame (RGB) with iris overlay drawn on it.
    eye_detected(float, float, float)
        Eye midpoint in centimetres ``(x, y, z)``.
    eye_lost()
        Emitted when no face / iris is detected in the current frame.
    """

    frame_ready = pyqtSignal(QImage)
    eye_detected = pyqtSignal(float, float, float)
    eye_lost = pyqtSignal()

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self._running = False
        self._config = TrackingConfig()

    # ── public API ──────────────────────────────────────────────────

    def update_config(self, config: TrackingConfig):
        """Replace the current tracking configuration (thread-safe for primitives)."""
        self._config = config

    def stop(self):
        """Request the thread to stop and wait for it to finish."""
        self._running = False
        if self.isRunning():
            self.wait(5000)

    # ── thread body ─────────────────────────────────────────────────

    def run(self):  # noqa: C901  — sequential I/O; splitting adds no clarity
        self._running = True
        cap = None
        face_mesh = None

        try:
            # CAP_DSHOW gives instant camera startup on Windows
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                self.eye_lost.emit()
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)

            face_mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

            while self._running:
                ret, frame = cap.read()
                if not ret:
                    self.msleep(10)
                    continue

                frame = cv2.flip(frame, 1)  # mirror for natural feel
                h, w, _ = frame.shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)

                if results.multi_face_landmarks:
                    lm = results.multi_face_landmarks[0].landmark
                    # MediaPipe iris-centre landmarks: left 468, right 473
                    left_iris = lm[468]
                    right_iris = lm[473]

                    eye_x_px = int((left_iris.x + right_iris.x) / 2 * w)
                    eye_y_px = int((left_iris.y + right_iris.y) / 2 * h)

                    # Draw overlays on the RGB frame
                    cv2.circle(rgb, (eye_x_px, eye_y_px), 6, (255, 50, 50), -1)
                    cv2.circle(rgb, (eye_x_px, eye_y_px), 10, (255, 100, 100), 2)

                    lx, ly = int(left_iris.x * w), int(left_iris.y * h)
                    rx, ry = int(right_iris.x * w), int(right_iris.y * h)
                    cv2.circle(rgb, (lx, ly), 3, (100, 200, 255), -1)
                    cv2.circle(rgb, (rx, ry), 3, (100, 200, 255), -1)

                    config = self._config
                    eye_cm = pixel_to_cm(
                        eye_x_px, eye_y_px, w, h,
                        config.screen_w_cm, config.screen_h_cm, config.eye_dist_cm,
                    )
                    self.eye_detected.emit(*eye_cm)
                else:
                    self.eye_lost.emit()

                # .copy() so Qt owns the buffer and it doesn't get overwritten
                bytes_per_line = 3 * w
                q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.frame_ready.emit(q_img)

        except Exception as error:
            print(f"Camera tracking stopped: {error}", file=sys.stderr)
            self.eye_lost.emit()
        finally:
            if face_mesh is not None:
                face_mesh.close()
            if cap is not None:
                cap.release()
            self._running = False
