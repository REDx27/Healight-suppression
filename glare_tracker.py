"""
Windshield Glare Tracking System — PyQt5 Desktop Application
=============================================================
Tracks driver eye position via webcam + MediaPipe, computes where an
eye-to-light-source ray intersects a virtual windshield plane (Y=0),
and visualizes everything in a 5-panel dashboard.

Usage:
    pip install -r requirements.txt
    python glare_tracker.py
"""

import sys
import time
import os
from dataclasses import dataclass

import numpy as np
import cv2
import mediapipe as mp

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QBrush, QRadialGradient, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QGroupBox,
    QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QPushButton, QDoubleSpinBox, QFrame, QSizePolicy, QComboBox,
    QScrollArea, QToolButton, QColorDialog, QGridLayout, QSlider
)

import pyqtgraph.opengl as gl
from pyqtgraph.opengl import GLTextItem
from OpenGL.GL import GL_LINES  # noqa: F401  — ensures PyOpenGL is importable


# ═══════════════════════════════════════════════════════════════════════════════
# GEOMETRY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TrackingConfig:
    screen_w_cm: float = 34.5
    screen_h_cm: float = 19.5
    eye_dist_cm: float = 50.0
    camera_x_cm: float = 0.0
    camera_y_cm: float = 0.0
    camera_z_cm: float = 30.0

def compute_intersection(eye_cm, light_cm):
    """
    Compute where the ray from *eye_cm* toward *light_cm* crosses the
    windshield plane at Y = 0. X is lateral, Y is front/back depth, and
    Z is vertical height.

    Parameters
    ----------
    eye_cm : tuple(float, float, float)
        Eye position in cm. Y should be negative (behind the windshield).
    light_cm : tuple(float, float, float)
        Light-source position in cm. Y should be positive (in front).

    Returns
    -------
    tuple(float, float, float) or None
        (x, 0.0, z) intersection point, or None if the ray is parallel to the plane.
    """
    x1, y1, z1 = eye_cm
    x2, y2, z2 = light_cm
    dy = y2 - y1
    if abs(dy) < 1e-9:
        return None
    t = -y1 / dy
    if not 0.0 <= t <= 1.0:
        return None
    return (x1 + t * (x2 - x1), 0.0, z1 + t * (z2 - z1))


def pixel_to_cm(eye_x_px, eye_y_px, frame_w, frame_h,
                screen_w_cm, screen_h_cm, eye_dist_cm):
    """
    Convert pixel-space iris midpoint to approximate real-world cm coordinates.

    The windshield is the vertical X-Z plane at Y = 0.
    The driver sits *behind* it at Y = -eye_dist_cm, with the eye height
    represented by the mapped screen coordinate.
    """
    x_cm = (eye_x_px - frame_w / 2) / frame_w * screen_w_cm
    y_cm = -eye_dist_cm
    z_cm = (frame_h / 2 - eye_y_px) / frame_h * screen_h_cm + screen_h_cm / 2
    return (x_cm, y_cm, z_cm)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VIDEO CAPTURE THREAD  (QThread + OpenCV + MediaPipe)
# ═══════════════════════════════════════════════════════════════════════════════

class VideoCaptureThread(QThread):
    """
    Runs in a background thread so the GUI never blocks.

    Signals
    -------
    frame_ready(QImage)
        BGR→RGB-converted camera frame with iris overlay drawn on it.
    eye_detected(float, float, float)
        Eye midpoint in cm: (x, y, z).
    eye_lost()
        Emitted when no face/iris is detected in the current frame.
    """
    frame_ready = pyqtSignal(QImage)
    eye_detected = pyqtSignal(float, float, float)
    eye_lost = pyqtSignal()

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self._running = False

        self._config = TrackingConfig()

    # ── public helpers ──────────────────────────────────────────────
    def update_config(self, config):
        self._config = config

    def stop(self):
        self._running = False
        if self.isRunning():
            self.wait(5000)

    # ── thread entry point ──────────────────────────────────────────
    def run(self):
        self._running = True
        cap = None
        face_mesh = None

        try:
            # Use DirectShow on Windows for instant camera startup
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

                # MediaPipe expects RGB
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)

                if results.multi_face_landmarks:
                    lm = results.multi_face_landmarks[0].landmark
                    # MediaPipe iris center landmarks: left 468, right 473
                    left_iris = lm[468]
                    right_iris = lm[473]

                    eye_x_px = int((left_iris.x + right_iris.x) / 2 * w)
                    eye_y_px = int((left_iris.y + right_iris.y) / 2 * h)

                    # Draw overlay on the RGB frame
                    cv2.circle(rgb, (eye_x_px, eye_y_px), 6, (255, 50, 50), -1)
                    cv2.circle(rgb, (eye_x_px, eye_y_px), 10, (255, 100, 100), 2)

                    # Draw both iris centers for visual verification
                    lx, ly = int(left_iris.x * w), int(left_iris.y * h)
                    rx, ry = int(right_iris.x * w), int(right_iris.y * h)
                    cv2.circle(rgb, (lx, ly), 3, (100, 200, 255), -1)
                    cv2.circle(rgb, (rx, ry), 3, (100, 200, 255), -1)

                    config = self._config
                    eye_cm = pixel_to_cm(
                        eye_x_px, eye_y_px, w, h,
                        config.screen_w_cm, config.screen_h_cm, config.eye_dist_cm
                    )
                    self.eye_detected.emit(*eye_cm)
                else:
                    self.eye_lost.emit()

                # Build QImage (must .copy() so Qt owns the buffer)
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


# ═══════════════════════════════════════════════════════════════════════════════
# 2. VIDEO WIDGET  (displays the camera feed)
# ═══════════════════════════════════════════════════════════════════════════════

class VideoWidget(QLabel):
    """Displays camera frames with aspect-ratio preservation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #1a1a2e; border: 1px solid #333;")
        self._pixmap = None

        # Show placeholder text
        self.setText("📹  Camera Feed\nClick 'Start Stream' to begin")
        self.setFont(QFont("Segoe UI", 11))

    def update_frame(self, q_img: QImage):
        self._pixmap = QPixmap.fromImage(q_img)
        self.setText("")
        self._rescale()

    def clear_feed(self):
        self._pixmap = None
        self.clear()
        self.setText("📹  Camera Feed\nStream stopped")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._pixmap:
            self.setPixmap(
                self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. WINDSHIELD 2D WIDGET  (top-down view with glowing glare spot)
# ═══════════════════════════════════════════════════════════════════════════════

class Windshield2DWidget(QWidget):
    """
    Custom-painted 2D front view of the windshield.
    Shows a glowing dot where the glare intersection lands.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 180)
        # Normalised position on windshield: (0,0)=top-left, (1,1)=bottom-right
        self._glares = []
        self._has_out_of_range = False

        # Windshield aspect ratio (updated from controls)
        self._ws_aspect = 34.5 / 19.4

    def set_windshield_aspect(self, w_cm, h_cm):
        if h_cm > 0:
            self._ws_aspect = w_cm / h_cm
        self.update()

    def update_glare(self, norm_x, norm_y, in_bounds):
        """Update glare position. norm_x/y in [0,1] range."""
        self.update_glares([(norm_x, norm_y, in_bounds)], not in_bounds)

    def update_glares(self, glares, has_out_of_range=False):
        """Update multiple glare positions as (norm_x, norm_y, in_bounds)."""
        self._glares = list(glares)
        self._has_out_of_range = has_out_of_range
        self.update()

    def clear_glare(self):
        self._glares = []
        self._has_out_of_range = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Dark background
        p.fillRect(self.rect(), QColor("#16213e"))

        # Reserve space for annotations so the title and edge labels stay
        # inside the widget when the dashboard is resized.
        margin = 18
        title_space = 24
        bottom_space = 22
        avail_w = max(1, self.width() - 2 * margin)
        avail_h = max(1, self.height() - 2 * margin - title_space - bottom_space)
        ws_w = min(avail_w, avail_h * self._ws_aspect)
        ws_h = ws_w / self._ws_aspect
        ws_x = (self.width() - ws_w) / 2
        ws_y = margin + title_space + (avail_h - ws_h) / 2

        # Windshield fill
        boundary_color = "#f44336" if self._has_out_of_range else "#0f4c75"
        p.setPen(QPen(QColor(boundary_color), 3 if self._has_out_of_range else 2))
        p.setBrush(QColor(15, 76, 117, 40))
        p.drawRoundedRect(int(ws_x), int(ws_y), int(ws_w), int(ws_h), 8, 8)

        # Grid crosshairs
        grid_pen = QPen(QColor(255, 255, 255, 30), 1, Qt.DashLine)
        p.setPen(grid_pen)
        cx = ws_x + ws_w / 2
        cy = ws_y + ws_h / 2
        p.drawLine(int(ws_x), int(cy), int(ws_x + ws_w), int(cy))
        p.drawLine(int(cx), int(ws_y), int(cx), int(ws_y + ws_h))

        # Labels
        label_font = QFont("Segoe UI", 8)
        p.setFont(label_font)
        p.setPen(QColor("#666"))
        p.drawText(int(cx - 10), int(ws_y - 6), "TOP")
        p.drawText(int(cx - 18), int(ws_y + ws_h + 16), "BOTTOM")
        p.drawText(max(4, int(ws_x - 28)), int(cy + 4), "LEFT")
        p.drawText(min(self.width() - 40, int(ws_x + ws_w + 4)), int(cy + 4), "RIGHT")

        # Title
        p.setPen(QColor("#bbe1fa"))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(max(8, int(ws_x)), margin + 16, "Windshield — Front View")

        # Glare spots
        for norm_x, norm_y, in_bounds in self._glares:
            spot_x = ws_x + norm_x * ws_w
            spot_y = ws_y + norm_y * ws_h

            from PyQt5.QtCore import QPointF
            center = QPointF(spot_x, spot_y)

            if in_bounds:
                # Glowing yellow/orange radial gradient
                radius = 28.0
                glow = QRadialGradient(center, radius)
                glow.setColorAt(0.0, QColor(255, 235, 59, 220))
                glow.setColorAt(0.4, QColor(255, 152, 0, 130))
                glow.setColorAt(1.0, QColor(255, 87, 34, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(glow))
                p.drawEllipse(center, radius, radius)

                # Core dot
                p.setBrush(QColor("#ffffff"))
                p.drawEllipse(center, 4, 4)
            else:
                # Out-of-bounds: red indicator with dashed circle
                p.setPen(QPen(QColor(255, 80, 80, 180), 2, Qt.DashLine))
                p.setBrush(QColor(255, 80, 80, 60))
                p.drawEllipse(center, 12, 12)

                # Clamp indicator lines to windshield edge
                p.setPen(QPen(QColor(255, 80, 80, 100), 1, Qt.DotLine))
                clamped_x = max(ws_x, min(ws_x + ws_w, spot_x))
                clamped_y = max(ws_y, min(ws_y + ws_h, spot_y))
                p.drawLine(int(clamped_x), int(clamped_y), int(spot_x), int(spot_y))

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 3D SCENE WIDGET  (PyQtGraph GLViewWidget wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

class Scene3DWidget(QWidget):
    """
    Wraps a pyqtgraph GLViewWidget and manages the 3D scene objects:
    windshield quad, eye point, light point, intersection point, and ray line.
    All items are created once and updated in-place via setData() for performance.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_colors = {
            "windshield": QColor("#00bfd6"),
            "eye": QColor("#4d80ff"),
            "light": QColor("#ff9800"),
        }
        self._eye_points_visible = True
        self._light_points_visible = True
        self._eye_label_size = 16
        self._light_label_size = 16
        self._offscreen_point = np.array([[9999, 9999, 9999]], dtype=np.float32)
        self._offscreen_line = np.array(
            [[9999, 9999, 9999], [9999, 9999, 9999]], dtype=np.float32
        )
        self._intersection_points = []
        self._last_light_positions = None
        self._last_eye_position = None
        self._last_ray_positions = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.gl_view = gl.GLViewWidget()
        self.gl_view.setBackgroundColor(QColor("#0a0a1a"))
        self.gl_view.setCameraPosition(distance=140, elevation=20, azimuth=-45)
        layout.addWidget(self.gl_view)

        # ── Grid ──
        grid = gl.GLGridItem()
        grid.setSize(200, 200, 1)
        grid.setSpacing(10, 10, 10)
        grid.setColor(QColor(255, 255, 255, 30))
        self.gl_view.addItem(grid)

        # ── Windshield quad (will be rebuilt when dimensions change) ──
        self._ws_mesh = None
        self._ws_w = 34.5
        self._ws_h = 19.5
        self._build_windshield(34.5, 19.5)

        # ── Axis lines ──
        axis_len = 50
        # X = red, Y = green, Z = blue
        for pts, color in [
            (np.array([[0, 0, 0], [axis_len, 0, 0]]), (1, 0.3, 0.3, 0.5)),
            (np.array([[0, 0, 0], [0, axis_len, 0]]), (0.3, 1, 0.3, 0.5)),
            (np.array([[0, 0, 0], [0, 0, axis_len]]), (0.3, 0.3, 1, 0.5)),
        ]:
            axis = gl.GLLinePlotItem(pos=pts, color=color, width=1.5, antialias=True)
            self.gl_view.addItem(axis)

        for text, pos, color in [
            ("X", (axis_len, 0, 0), (1.0, 0.3, 0.3, 1.0)),
            ("Y", (0, axis_len, 0), (0.3, 1.0, 0.3, 1.0)),
            ("Z", (0, 0, axis_len), (0.3, 0.3, 1.0, 1.0)),
        ]:
            axis_label = GLTextItem(pos=pos, text=text, color=color)
            self.gl_view.addItem(axis_label)

        self._light_scatters = []
        self._light_labels = []
        self._inter_scatters = []
        self._inter_labels = []
        self._ray_lines = []
        for index in range(4):
            light_scatter = gl.GLScatterPlotItem(
                pos=np.array([[9999, 9999, 9999]], dtype=np.float32),
                size=14, color=(1.0, 0.6, 0.0, 1.0), pxMode=True
            )
            self.gl_view.addItem(light_scatter)
            self._light_scatters.append(light_scatter)

            light_label = GLTextItem(
                pos=(9999, 9999, 9999), text=f"Light Source {index + 1}",
                color=(1.0, 0.7, 0.2, 1.0)
            )
            self.gl_view.addItem(light_label)
            self._light_labels.append(light_label)

            inter_scatter = gl.GLScatterPlotItem(
                pos=np.array([[9999, 9999, 9999]], dtype=np.float32),
                size=22, color=(1.0, 0.95, 0.2, 1.0), pxMode=True
            )
            self.gl_view.addItem(inter_scatter)
            self._inter_scatters.append(inter_scatter)

            inter_label = GLTextItem(
                pos=(9999, 9999, 9999), text=f"Intersection {index + 1}",
                color=(1.0, 0.95, 0.2, 1.0)
            )
            self.gl_view.addItem(inter_label)
            self._inter_labels.append(inter_label)

            ray_line = gl.GLLinePlotItem(
                pos=np.array([[9999, 9999, 9999], [9999, 9999, 9999]], dtype=np.float32),
                color=(1.0, 0.2, 0.2, 0.8), width=2.5, antialias=True
            )
            self.gl_view.addItem(ray_line)
            self._ray_lines.append(ray_line)

        # ── Eye point (blue), behind the windshield and above the floor ──
        self._eye_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, -50, 10]], dtype=np.float32),
            size=12, color=(0.3, 0.5, 1.0, 1.0), pxMode=True
        )
        self.gl_view.addItem(self._eye_scatter)
        self._eye_label = GLTextItem(
            pos=(9999, 9999, 9999), text="Driver Eye", color=(0.4, 0.6, 1.0, 1.0)
        )
        self.gl_view.addItem(self._eye_label)
        self._camera_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, 0, 30]], dtype=np.float32),
            size=10, color=(0.8, 0.8, 0.8, 1.0), pxMode=True
        )
        self.gl_view.addItem(self._camera_scatter)
        self._camera_label = GLTextItem(
            pos=(0, 0, 30), text="Webcam", color=(0.8, 0.8, 0.8, 1.0)
        )
        self.gl_view.addItem(self._camera_label)
        self._eye_visible = False
        self._active_light_count = 0

        self._build_scene_settings()

        # Start with tracking items hidden
        self._hide_tracking()

    def _build_scene_settings(self):
        """Create the compact settings overlay anchored to the 3D corner."""
        self.settings_button = QToolButton(self)
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("3D view settings")
        self.settings_button.setFixedSize(36, 36)
        self.settings_button.clicked.connect(self._toggle_scene_settings)

        self.settings_panel = QFrame(self)
        self.settings_panel.setObjectName("sceneSettingsPanel")
        self.settings_panel.setStyleSheet(
            "QFrame#sceneSettingsPanel { background: rgba(13, 17, 23, 235); "
            "border: 1px solid #30363d; border-radius: 6px; }"
            "QLabel { color: #c9d1d9; }"
            "QToolButton { color: #c9d1d9; background: #21262d; border: 1px solid #30363d; "
            "border-radius: 4px; padding: 4px; }"
            "QToolButton:checked { background: #0d419d; border-color: #58a6ff; }"
            "QPushButton { border: 1px solid #30363d; border-radius: 3px; min-width: 34px; "
            "min-height: 22px; }"
        )
        panel_layout = QGridLayout(self.settings_panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(6)
        panel_layout.addWidget(QLabel("3D view"), 0, 0, 1, 2)
        self._add_color_control(panel_layout, 1, "Windshield", "windshield")
        self._add_color_control(panel_layout, 2, "Driver eye", "eye")
        self._add_color_control(panel_layout, 3, "Light source", "light")
        self._add_label_size_control(panel_layout, 4, "Eye label size", "eye")
        self._add_label_size_control(panel_layout, 5, "Light label size", "light")

        self.eye_toggle = QToolButton()
        self.eye_toggle.setText("👁  Eye points")
        self.eye_toggle.setToolTip("Show or hide driver eye points")
        self.eye_toggle.setCheckable(True)
        self.eye_toggle.setChecked(True)
        self.eye_toggle.clicked.connect(self._toggle_eye_points)

        self.light_toggle = QToolButton()
        self.light_toggle.setText("☀  Light points")
        self.light_toggle.setToolTip("Show or hide light source points")
        self.light_toggle.setCheckable(True)
        self.light_toggle.setChecked(True)
        self.light_toggle.clicked.connect(self._toggle_light_points)
        panel_layout.addWidget(self.eye_toggle, 6, 0, 1, 2)
        panel_layout.addWidget(self.light_toggle, 7, 0, 1, 2)
        self.settings_panel.adjustSize()
        self.settings_panel.hide()

    def _add_color_control(self, layout, row, label, color_key):
        layout.addWidget(QLabel(label), row, 0)
        button = QPushButton()
        button.setToolTip(f"Change {label.lower()} color")
        button.clicked.connect(lambda: self._choose_scene_color(color_key))
        setattr(self, f"_{color_key}_color_button", button)
        self._update_color_button(button, self._scene_colors[color_key])
        layout.addWidget(button, row, 1)

    def _add_label_size_control(self, layout, row, label, label_key):
        layout.addWidget(QLabel(label), row, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(8, 32)
        slider.setValue(
            self._eye_label_size if label_key == "eye" else self._light_label_size
        )
        slider.setToolTip(f"Change {label.lower()}")
        slider.valueChanged.connect(
            lambda value: self._set_label_size(label_key, value)
        )
        setattr(self, f"_{label_key}_label_slider", slider)
        layout.addWidget(slider, row, 1)

    def _set_label_size(self, label_key, size):
        font = QFont("Segoe UI", size)
        if label_key == "eye":
            self._eye_label_size = size
            self._eye_label.setData(font=font)
        else:
            self._light_label_size = size
            for label in self._light_labels:
                label.setData(font=font)

    @staticmethod
    def _update_color_button(button, color):
        button.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #ffffff; "
            "border-radius: 3px; min-width: 34px; min-height: 22px;"
        )

    def _choose_scene_color(self, color_key):
        color = QColorDialog.getColor(self._scene_colors[color_key], self, "Choose 3D color")
        if color.isValid():
            self._scene_colors[color_key] = color
            self._update_color_button(getattr(self, f"_{color_key}_color_button"), color)
            self._apply_scene_colors()

    def _apply_scene_colors(self):
        windshield = self._scene_colors["windshield"]
        eye = self._scene_colors["eye"]
        light = self._scene_colors["light"]
        self._build_windshield(self._ws_w, self._ws_h)
        for scatter in self._light_scatters:
            scatter.setData(color=light)
        for label in self._light_labels:
            label.setData(color=light)
        self._eye_scatter.setData(color=eye)
        self._eye_label.setData(color=eye)

    def _toggle_scene_settings(self):
        self.settings_panel.setVisible(not self.settings_panel.isVisible())
        self._position_scene_controls()

    def _toggle_eye_points(self, visible):
        self._eye_points_visible = visible
        self._eye_scatter.setVisible(visible)
        self._eye_label.setVisible(visible)

    def _toggle_light_points(self, visible):
        self._light_points_visible = visible
        for scatter, label in zip(self._light_scatters, self._light_labels):
            scatter.setVisible(visible)
            label.setVisible(visible)

    def _position_scene_controls(self):
        margin = 10
        self.settings_button.move(self.width() - self.settings_button.width() - margin, margin)
        self.settings_button.raise_()
        if self.settings_panel.isVisible():
            self.settings_panel.adjustSize()
            self.settings_panel.move(
                self.width() - self.settings_panel.width() - margin,
                self.settings_button.height() + margin * 2,
            )
            self.settings_panel.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_scene_controls()

    def _build_windshield(self, w_cm, h_cm):
        """Create or replace the windshield mesh in the vertical X-Z plane at Y=0."""
        hw, hh = w_cm / 2, h_cm / 2
        verts = np.array([
            [-hw, 0, 0],
            [hw, 0, 0],
            [hw, 0, h_cm],
            [-hw, 0, h_cm],
        ], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]])

        color = self._scene_colors["windshield"]
        colors = np.array([
            [color.redF(), color.greenF(), color.blueF(), 0.25],
            [color.redF(), color.greenF(), color.blueF(), 0.25],
        ], dtype=np.float32)

        mesh_kwargs = {
            "vertexes": verts,
            "faces": faces,
            "faceColors": colors,
            "smooth": False,
            "drawEdges": True,
            "edgeColor": (color.redF(), color.greenF(), color.blueF(), 0.8),
        }
        if self._ws_mesh is None:
            self._ws_mesh = gl.GLMeshItem(**mesh_kwargs)
            self.gl_view.addItem(self._ws_mesh)
        else:
            self._ws_mesh.setMeshData(**mesh_kwargs)
        self._ws_w = w_cm
        self._ws_h = h_cm
        if hasattr(self, "_inter_scatters"):
            self._restore_intersections()

    def update_windshield(self, w_cm, h_cm):
        if abs(w_cm - self._ws_w) > 0.01 or abs(h_cm - self._ws_h) > 0.01:
            self._build_windshield(w_cm, h_cm)

    def update_light(self, x, y, z):
        self.update_lights([(x, y, z)])

    def update_lights(self, light_positions):
        positions = tuple(tuple(position) for position in light_positions[:4])
        if positions == self._last_light_positions:
            return
        self._last_light_positions = positions
        self._active_light_count = min(4, len(light_positions))
        for index in range(4):
            if index < self._active_light_count:
                position = np.array([light_positions[index]], dtype=np.float32)
                self._light_scatters[index].setData(pos=position)
                self._light_labels[index].setData(pos=light_positions[index])
            else:
                self._light_scatters[index].setData(pos=self._offscreen_point)
                self._light_labels[index].setData(pos=(9999, 9999, 9999))

    def update_eye(self, x, y, z):
        position = (x, y, z)
        if position == self._last_eye_position:
            return
        self._last_eye_position = position
        self._eye_scatter.setData(pos=np.array([[x, y, z]], dtype=np.float32))
        self._eye_label.setData(pos=(x, y, z))
        if not self._eye_visible:
            self._eye_visible = True

    def update_camera(self, x, y, z):
        self._camera_scatter.setData(pos=np.array([[x, y, z]], dtype=np.float32))
        self._camera_label.setData(pos=(x, y, z))

    def update_intersection(self, ix, iy, iz):
        self.update_intersections([(ix, iy, iz)])

    def update_intersections(self, intersections):
        self._intersection_points = list(intersections[:4])
        self._restore_intersections()

    def _restore_intersections(self):
        """Restore markers after mesh replacement without recalculating tracking."""
        offscreen = self._offscreen_point
        for index in range(4):
            if index < len(self._intersection_points):
                point = self._intersection_points[index]
                # Offset toward the driver so the marker is visible in front of
                # the windshield mesh while its calculated X/Z stay unchanged.
                display_point = (point[0], -0.6, point[2])
                self._inter_scatters[index].setData(
                    pos=np.array([display_point], dtype=np.float32)
                )
                self._inter_labels[index].setData(pos=display_point)
            else:
                self._inter_scatters[index].setData(pos=offscreen)
                self._inter_labels[index].setData(pos=(9999, 9999, 9999))

    def update_ray(self, eye_cm, light_cm):
        self.update_rays(eye_cm, [light_cm])

    def update_rays(self, eye_cm, light_positions):
        ray_positions = (tuple(eye_cm), *(tuple(position) for position in light_positions[:4]))
        if ray_positions == self._last_ray_positions:
            return
        self._last_ray_positions = ray_positions
        for index in range(4):
            if index < len(light_positions):
                points = np.array([list(eye_cm), list(light_positions[index])], dtype=np.float32)
                self._ray_lines[index].setData(pos=points)
            else:
                self._ray_lines[index].setData(pos=self._offscreen_line)
        if light_positions:
            self._ray_visible = True

    def _hide_tracking(self):
        """Move tracking items off-screen when no face detected."""
        offscreen = self._offscreen_point
        self._intersection_points = []
        self._last_eye_position = None
        self._last_ray_positions = None
        self._eye_scatter.setData(pos=offscreen)
        self._eye_label.setData(pos=(9999, 9999, 9999))
        for scatter, label in zip(self._inter_scatters, self._inter_labels):
            scatter.setData(pos=offscreen)
            label.setData(pos=(9999, 9999, 9999))
        for ray in self._ray_lines:
            ray.setData(pos=self._offscreen_line)
        self._eye_visible = False
        self._ray_visible = False

    def hide_tracking(self):
        self._hide_tracking()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. READOUT PANEL  (telemetry text)
# ═══════════════════════════════════════════════════════════════════════════════

class ReadoutPanel(QGroupBox):
    """Monospace telemetry readout showing coordinates and status."""

    def __init__(self, parent=None):
        super().__init__("📊 Telemetry", parent)
        layout = QFormLayout(self)
        layout.setSpacing(6)

        mono = QFont("Consolas", 10)
        self._labels = {}

        fields = [
            ("eye_pos", "Eye Position"),
            ("light_pos", "Light Sources"),
            ("fps", "Frame Rate"),
            ("status", "Tracking"),
        ]

        for key, label_text in fields:
            lbl = QLabel("—")
            lbl.setFont(mono)
            lbl.setStyleSheet(
                "color: #4caf50; background-color: #0d1117; "
                "padding: 4px 8px; border-radius: 3px; border: 1px solid #222;"
            )
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addRow(f"{label_text}:", lbl)
            self._labels[key] = lbl

        self._intersection_box = QGroupBox("Windshield Intersections")
        self._intersection_layout = QVBoxLayout(self._intersection_box)
        self._intersection_labels = []
        layout.addRow(self._intersection_box)

    def set_intersections(self, intersections):
        while self._intersection_labels:
            label = self._intersection_labels.pop()
            self._intersection_layout.removeWidget(label)
            label.deleteLater()

        for index, (point, in_bounds) in enumerate(intersections, start=1):
            if point is None:
                text = f"Intersection {index}: No mathematical intersection"
                color = "#f44336"
            elif not in_bounds:
                ix, _, iz = point
                text = (
                    f"Intersection {index}: Out of Range — No valid "
                    f"windshield intersection (X:{ix:7.1f} Z:{iz:7.1f})"
                )
                color = "#f44336"
            else:
                ix, _, iz = point
                text = f"Intersection {index}: X:{ix:7.1f}  Z:{iz:7.1f}  YES"
                color = "#4caf50"
            label = QLabel(text)
            label.setFont(QFont("Consolas", 9))
            label.setStyleSheet(
                f"color: {color}; background-color: #0d1117; padding: 4px 8px; "
                "border-radius: 3px; border: 1px solid #222;"
            )
            self._intersection_layout.addWidget(label)
            self._intersection_labels.append(label)

        if not intersections:
            label = QLabel("—")
            label.setFont(QFont("Consolas", 9))
            self._intersection_layout.addWidget(label)
            self._intersection_labels.append(label)

    def set_value(self, key, text, color=None):
        if key in self._labels:
            self._labels[key].setText(text)
            if color:
                self._labels[key].setStyleSheet(
                    f"color: {color}; background-color: #0d1117; "
                    "padding: 4px 8px; border-radius: 3px; border: 1px solid #222;"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. CONTROLS PANEL  (inputs, buttons)
# ═══════════════════════════════════════════════════════════════════════════════

class ControlsPanel(QGroupBox):
    """User-configurable parameters for the tracking system."""

    def __init__(self, parent=None):
        super().__init__("⚙ Controls", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Windshield Dimensions ──
        ws_group = QGroupBox("Windshield (cm)")
        ws_layout = QFormLayout(ws_group)

        self.spin_ws_w = self._make_spin(1.0, 500.0, 34.5, " cm")
        self.spin_ws_h = self._make_spin(1.0, 500.0, 19.5, " cm")

        ws_layout.addRow("Width:", self.spin_ws_w)
        ws_layout.addRow("Height:", self.spin_ws_h)
        layout.addWidget(ws_group)

        # ── Camera and eye distance ──
        camera_group = QGroupBox("Camera Position (cm)")
        camera_layout = QFormLayout(camera_group)
        self.spin_camera_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_y = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_z = self._make_spin(-1000, 1000, 30.0, " cm")
        camera_layout.addRow("X:", self.spin_camera_x)
        camera_layout.addRow("Y:", self.spin_camera_y)
        camera_layout.addRow("Z:", self.spin_camera_z)
        layout.addWidget(camera_group)

        dist_group = QGroupBox("Driver Distance (cm)")
        dist_layout = QFormLayout(dist_group)

        self.spin_eye_dist = self._make_spin(5.0, 500.0, 50.0, " cm")
        self.distance_note = QLabel("Manual/reference measurement")
        self.distance_note.setStyleSheet("color: #8b949e;")
        dist_layout.addRow("Distance:", self.spin_eye_dist)
        dist_layout.addRow(self.distance_note)
        layout.addWidget(dist_group)

        # ── Vehicle/light mode ──
        vehicle_group = QGroupBox("Vehicle / Light Mode")
        vehicle_layout = QFormLayout(vehicle_group)
        self.combo_vehicle = QComboBox()
        self.combo_vehicle.addItems(["Motorcycle", "Four-Wheeler/Car", "Extreme Vehicle"])
        vehicle_layout.addRow("Category:", self.combo_vehicle)
        layout.addWidget(vehicle_group)

        # ── Light Source Position ──
        light_group = QGroupBox("Light Source (cm)")
        light_layout = QFormLayout(light_group)

        self.spin_light_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_light_y = self._make_spin(-1000, 1000, 120.0, " cm")
        self.spin_light_z = self._make_spin(-1000, 5000, 10.0, " cm")

        light_layout.addRow("X:", self.spin_light_x)
        light_layout.addRow("Y:", self.spin_light_y)
        light_layout.addRow("Z:", self.spin_light_z)
        layout.addWidget(light_group)

        # ── Light movement demonstration ──
        self.combo_movement = QComboBox()
        self.combo_movement.addItems([
            "Coming straight",
            "Coming at the opposite side",
            "Long distance",
        ])
        self.btn_play_movement = QPushButton("▶  Play Light Movement")
        self.btn_play_movement.setCheckable(True)
        self.btn_play_movement.setMinimumHeight(32)
        layout.addWidget(self.combo_movement)
        layout.addWidget(self.btn_play_movement)

        # ── Buttons ──
        self.btn_stream = QPushButton("▶  Start Stream")
        self.btn_stream.setCheckable(True)
        self.btn_stream.setMinimumHeight(36)
        self.btn_stream.setStyleSheet(
            "QPushButton { background-color: #1b5e20; color: white; font-weight: bold; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:checked { background-color: #b71c1c; }"
        )

        self.btn_calibrate = QPushButton("🎯  Calibrate Center")
        self.btn_calibrate.setMinimumHeight(32)

        self.btn_reset_view = QPushButton("🔄  Reset 3D View")
        self.btn_reset_view.setMinimumHeight(32)

        layout.addSpacing(8)
        layout.addWidget(self.btn_stream)
        layout.addWidget(self.btn_calibrate)
        layout.addWidget(self.btn_reset_view)
        layout.addStretch()

    def _make_spin(self, min_val, max_val, default, suffix=""):
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSuffix(suffix)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setMinimumHeight(28)
        return spin

    def get_light_pos(self):
        return (self.spin_light_x.value(),
                self.spin_light_y.value(),
                self.spin_light_z.value())

    def get_light_positions(self):
        base_x, base_y, base_z = self.get_light_pos()
        category = self.combo_vehicle.currentText()
        if category == "Four-Wheeler/Car":
            offsets = [(-8.0, 0.0, 0.0), (8.0, 0.0, 0.0)]
        elif category == "Extreme Vehicle":
            offsets = [(-10.0, 0.0, -4.0), (10.0, 0.0, -4.0),
                       (-10.0, 0.0, 4.0), (10.0, 0.0, 4.0)]
        else:
            offsets = [(0.0, 0.0, 0.0)]
        return [(base_x + dx, base_y + dy, base_z + dz)
                for dx, dy, dz in offsets]

    def get_windshield_dims(self):
        return (self.spin_ws_w.value(), self.spin_ws_h.value())

    def get_eye_distance(self):
        return self.spin_eye_dist.value()

    def get_camera_pos(self):
        return (self.spin_camera_x.value(), self.spin_camera_y.value(), self.spin_camera_z.value())


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MAIN WINDOW  (assembles all panels)
# ═══════════════════════════════════════════════════════════════════════════════

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: "Segoe UI", sans-serif;
}
QGroupBox {
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #58a6ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QDoubleSpinBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px;
    color: #c9d1d9;
}
QDoubleSpinBox:focus {
    border-color: #58a6ff;
}
QPushButton {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 6px 12px;
    color: #c9d1d9;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
}
QPushButton:pressed {
    background-color: #0d419d;
}
QSplitter::handle {
    background-color: #21262d;
}
QSplitter::handle:horizontal {
    width: 3px;
}
QSplitter::handle:vertical {
    height: 3px;
}
QLabel {
    color: #c9d1d9;
}
"""


class MainWindow(QMainWindow):
    """
    Main application window assembling all 5 panels with nested QSplitters.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Windshield Glare Tracking System")
        self.setWindowIcon(self._application_icon())
        self.resize(1400, 850)
        self.setStyleSheet(DARK_STYLESHEET)

        # ── Instantiate panels ──
        self.video_widget = VideoWidget()
        self.windshield_2d = Windshield2DWidget()
        self.scene_3d = Scene3DWidget()
        self.readout = ReadoutPanel()
        self.controls = ControlsPanel()

        # ── Layout with nested QSplitters ──
        # Top row: Camera | 2D Windshield
        self.top_splitter = QSplitter(Qt.Horizontal)
        self.top_splitter.addWidget(self.video_widget)
        self.top_splitter.addWidget(self.windshield_2d)
        self.top_splitter.setSizes([550, 400])
        self.top_splitter.setStretchFactor(0, 1)
        self.top_splitter.setStretchFactor(1, 1)

        # Left column: top row above, 3D below
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.addWidget(self.top_splitter)
        self.left_splitter.addWidget(self.scene_3d)
        self.left_splitter.setSizes([320, 480])
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 1)

        # Right sidebar with scrolling for the full controls/readout stack
        sidebar_content = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_content)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        sidebar_layout.addWidget(self.readout)
        sidebar_layout.addWidget(self.controls)
        sidebar_layout.addStretch()

        sidebar = QScrollArea()
        sidebar.setWidgetResizable(True)
        sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sidebar.setWidget(sidebar_content)
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(420)

        # Main splitter: left viewport | right sidebar
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(sidebar)
        self.main_splitter.setSizes([1050, 350])
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(12, 12, 12, 12)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.main_splitter)
        self.setCentralWidget(central_widget)

        # ── Camera thread ──
        self.cap_thread = VideoCaptureThread()

        # ── State ──
        self._last_eye_cm = None
        self._last_observed_eye_cm = None
        self._calibration_offset = (0.0, 0.0, 0.0)
        self._baseline_captured = False
        self._frame_times = []
        self._simulation_lights = None
        self._movement_phase = 0.0

        # ── Connect signals ──
        self.cap_thread.frame_ready.connect(self.video_widget.update_frame)
        self.cap_thread.eye_detected.connect(self._on_eye_detected)
        self.cap_thread.eye_lost.connect(self._on_eye_lost)

        self.controls.btn_stream.clicked.connect(self._toggle_stream)
        self.controls.btn_calibrate.clicked.connect(self._on_calibrate)
        self.controls.btn_reset_view.clicked.connect(self._on_reset_3d_view)
        self.controls.btn_play_movement.clicked.connect(self._toggle_light_movement)

        # React to parameter changes
        self.controls.spin_ws_w.valueChanged.connect(self._on_params_changed)
        self.controls.spin_ws_h.valueChanged.connect(self._on_params_changed)
        self.controls.spin_eye_dist.valueChanged.connect(self._on_params_changed)
        self.controls.spin_camera_x.valueChanged.connect(self._on_params_changed)
        self.controls.spin_camera_y.valueChanged.connect(self._on_params_changed)
        self.controls.spin_camera_z.valueChanged.connect(self._on_params_changed)
        self.controls.spin_light_x.valueChanged.connect(self._on_params_changed)
        self.controls.spin_light_y.valueChanged.connect(self._on_params_changed)
        self.controls.spin_light_z.valueChanged.connect(self._on_params_changed)
        self.controls.combo_vehicle.currentIndexChanged.connect(self._on_params_changed)

        # Initial parameter push
        self._on_params_changed()

        # ── FPS timer ──
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)

        self._movement_timer = QTimer(self)
        self._movement_timer.setInterval(50)
        self._movement_timer.timeout.connect(self._advance_light_movement)

    @staticmethod
    def _application_icon():
        if getattr(sys, "frozen", False):
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return QIcon(os.path.join(base_path, "assets", "glaretracker-icon.ico"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 1050
        self.main_splitter.setOrientation(Qt.Vertical if narrow else Qt.Horizontal)
        if narrow:
            self.main_splitter.widget(1).setMinimumWidth(0)
            self.main_splitter.widget(1).setMaximumWidth(16777215)
        else:
            self.main_splitter.widget(1).setMinimumWidth(280)
            self.main_splitter.widget(1).setMaximumWidth(420)

    # ── Stream control ─────────────────────────────────────────────
    def _toggle_stream(self, checked):
        if checked:
            if self.cap_thread.isRunning():
                return
            self.controls.btn_stream.setText("⏹  Stop Stream")
            self._push_config_to_thread()
            self.cap_thread.start()
            self.readout.set_value("status", "ACTIVE ●", "#4caf50")
        else:
            self.controls.btn_stream.setText("▶  Start Stream")
            self.cap_thread.stop()
            self.video_widget.clear_feed()
            self.scene_3d.hide_tracking()
            self.windshield_2d.clear_glare()
            self.readout.set_value("status", "STOPPED ○", "#666")

    def _push_config_to_thread(self):
        self.cap_thread.update_config(TrackingConfig(
            self.controls.spin_ws_w.value(),
            self.controls.spin_ws_h.value(),
            self.controls.spin_eye_dist.value(),
            *self.controls.get_camera_pos(),
        ))

    def _toggle_light_movement(self, playing):
        if playing:
            self._movement_phase = 0.0
            self._simulation_lights = self._movement_positions()
            self.controls.btn_play_movement.setText("⏹  Stop Light Movement")
            self._movement_timer.start()
            self._process_tracking(self._last_eye_cm or (0.0, -50.0, 9.75))
        else:
            self._movement_timer.stop()
            self._simulation_lights = None
            self.controls.btn_play_movement.setText("▶  Play Light Movement")
            self._on_params_changed()

    def _advance_light_movement(self):
        self._movement_phase = (self._movement_phase + 0.0125) % 1.0
        self._simulation_lights = self._movement_positions()
        self._process_tracking(self._last_eye_cm or (0.0, -50.0, 9.75))

    def _movement_positions(self):
        """Move the configured lights as one rigid vehicle through the scene."""
        phase = self._movement_phase
        mode = self.controls.combo_movement.currentText()
        base_lights = self.controls.get_light_positions()
        if not base_lights:
            return []

        # Every source receives the same vehicle translation. Keeping the
        # offsets fixed preserves the physical headlight arrangement; the
        # ray calculation supplies the perspective convergence at distance.
        base_x = sum(position[0] for position in base_lights) / len(base_lights)
        base_y = sum(position[1] for position in base_lights) / len(base_lights)
        base_z = sum(position[2] for position in base_lights) / len(base_lights)
        if mode == "Coming at the opposite side":
            vehicle_x = base_x - 90.0 + 180.0 * phase
            vehicle_y = base_y
            vehicle_z = base_z
        elif mode == "Long distance":
            vehicle_x = base_x
            vehicle_y = base_y + 700.0 - 580.0 * phase
            vehicle_z = base_z
        else:
            vehicle_x = base_x + 4.0 * np.sin(phase * 2 * np.pi)
            vehicle_y = base_y + 240.0 - 210.0 * phase
            vehicle_z = base_z

        return [
            (vehicle_x + (light_x - base_x),
             vehicle_y + (light_y - base_y),
             vehicle_z + (light_z - base_z))
            for light_x, light_y, light_z in base_lights
        ]

    # ── Parameter changes ──────────────────────────────────────────
    def _on_params_changed(self):
        ws_w, ws_h = self.controls.get_windshield_dims()
        lights = self.controls.get_light_positions()

        # Update 3D scene
        self.scene_3d.update_windshield(ws_w, ws_h)
        self.scene_3d.update_lights(lights)
        self.scene_3d.update_camera(*self.controls.get_camera_pos())

        # Update 2D windshield aspect
        self.windshield_2d.set_windshield_aspect(ws_w, ws_h)

        # Update readout
        self.readout.set_value(
            "light_pos",
            f"{len(lights)} source(s) — {self.controls.combo_vehicle.currentText()}"
        )

        # Push to thread if running
        if self.cap_thread.isRunning():
            self._push_config_to_thread()

        # Recalculate with last known eye position
        if self._last_eye_cm:
            self._process_tracking(self._last_eye_cm)

    # ── Eye tracking callbacks ─────────────────────────────────────
    def _on_eye_detected(self, x, y, z):
        observed = (x, y, z)
        self._last_observed_eye_cm = observed
        if not self._baseline_captured:
            self._capture_baseline(observed)
        adjusted = (x - self._calibration_offset[0],
                    y - self._calibration_offset[1],
                    z - self._calibration_offset[2])
        self._last_eye_cm = adjusted
        self._frame_times.append(time.time())
        self._process_tracking(adjusted)

    def _capture_baseline(self, observed_eye_cm):
        ws_h = self.controls.get_windshield_dims()[1]
        self._calibration_offset = (
            observed_eye_cm[0],
            0.0,
            observed_eye_cm[2] - ws_h / 2,
        )
        self._baseline_captured = True

    def _process_tracking(self, eye_cm):
        lights = self._simulation_lights or self.controls.get_light_positions()
        ws_w, ws_h = self.controls.get_windshield_dims()

        # Update 3D: eye + ray
        self.scene_3d.update_eye(*eye_cm)
        self.scene_3d.update_lights(lights)
        self.scene_3d.update_rays(eye_cm, lights)

        intersections = []
        valid_intersections = []
        glare_points = []
        hw = ws_w / 2
        for light in lights:
            intersection = compute_intersection(eye_cm, light)
            if intersection is None:
                intersections.append((None, False))
                continue
            ix, iy, iz = intersection
            in_bounds = (-hw <= ix <= hw) and (0.0 <= iz <= ws_h)
            intersections.append((intersection, in_bounds))
            glare_points.append(((ix + hw) / ws_w, (ws_h - iz) / ws_h, in_bounds))
            if in_bounds:
                valid_intersections.append(intersection)

        self.scene_3d.update_intersections(valid_intersections)

        # Update readout: eye
        self.readout.set_value(
            "eye_pos",
            f"X:{eye_cm[0]:7.1f}  Y:{eye_cm[1]:7.1f}  Z:{eye_cm[2]:7.1f}",
            "#58a6ff"
        )
        self.readout.set_value("status", "TRACKING ●", "#4caf50")

        self.readout.set_intersections(intersections)
        if intersections:
            self.windshield_2d.update_glares(
                glare_points,
                any(point is not None and not in_bounds for point, in_bounds in intersections)
            )
        else:
            self.windshield_2d.clear_glare()

    def _on_eye_lost(self):
        self._last_eye_cm = None
        self.scene_3d.hide_tracking()
        self.windshield_2d.clear_glare()
        self.readout.set_value("eye_pos", "— (no face detected)", "#f44336")
        self.readout.set_intersections([])
        self.readout.set_value("status", "NO FACE ●", "#f44336")

    # ── Calibration ────────────────────────────────────────────────
    def _on_calibrate(self):
        """Capture the current observed eye as the fixed windshield-center baseline."""
        if self._last_observed_eye_cm:
            self._capture_baseline(self._last_observed_eye_cm)
            self.readout.set_value("status", "CALIBRATED ✓", "#4caf50")
        else:
            self.readout.set_value("status", "Calibration failed — no face", "#f44336")

    # ── 3D View reset ──────────────────────────────────────────────
    def _on_reset_3d_view(self):
        self.scene_3d.gl_view.setCameraPosition(distance=140, elevation=20, azimuth=-45)

    # ── FPS counter ────────────────────────────────────────────────
    def _update_fps(self):
        now = time.time()
        # Keep only last 2 seconds of timestamps
        self._frame_times = [t for t in self._frame_times if now - t < 2.0]
        if len(self._frame_times) > 1:
            fps = len(self._frame_times) / 2.0
            self.readout.set_value("fps", f"{fps:.1f} FPS", "#4caf50" if fps > 20 else "#ff9800")
        else:
            self.readout.set_value("fps", "— FPS", "#666")

    # ── Clean shutdown ─────────────────────────────────────────────
    def closeEvent(self, event):
        self._movement_timer.stop()
        self.cap_thread.stop()
        if self.cap_thread.isRunning():
            event.ignore()
            return
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # consistent cross-platform look
    app.setWindowIcon(MainWindow._application_icon())

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
