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
import math
import numpy as np
import cv2
import mediapipe as mp

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QBrush, QRadialGradient, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QGroupBox,
    QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QPushButton, QDoubleSpinBox, QFrame, QSizePolicy
)

import pyqtgraph.opengl as gl
from OpenGL.GL import GL_LINES  # noqa: F401  — ensures PyOpenGL is importable


# ═══════════════════════════════════════════════════════════════════════════════
# GEOMETRY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

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

        # Configurable parameters (updated from GUI controls)
        self.screen_w_cm = 34.5
        self.screen_h_cm = 19.4
        self.eye_dist_cm = 50.0

    # ── public helpers ──────────────────────────────────────────────
    def update_config(self, screen_w, screen_h, eye_dist):
        self.screen_w_cm = screen_w
        self.screen_h_cm = screen_h
        self.eye_dist_cm = eye_dist

    def stop(self):
        self._running = False
        self.wait(3000)

    # ── thread entry point ──────────────────────────────────────────
    def run(self):
        self._running = True

        # Use DirectShow on Windows for instant camera startup
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
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
                # Iris landmarks: left 474, right 469
                left_iris = lm[474]
                right_iris = lm[469]

                eye_x_px = int((left_iris.x + right_iris.x) / 2 * w)
                eye_y_px = int((left_iris.y + right_iris.y) / 2 * h)

                # Draw overlay on the RGB frame
                cv2.circle(rgb, (eye_x_px, eye_y_px), 6, (255, 50, 50), -1)
                cv2.circle(rgb, (eye_x_px, eye_y_px), 10, (255, 100, 100), 2)

                # Optional: draw both iris centers
                lx, ly = int(left_iris.x * w), int(left_iris.y * h)
                rx, ry = int(right_iris.x * w), int(right_iris.y * h)
                cv2.circle(rgb, (lx, ly), 3, (100, 200, 255), -1)
                cv2.circle(rgb, (rx, ry), 3, (100, 200, 255), -1)

                eye_cm = pixel_to_cm(
                    eye_x_px, eye_y_px, w, h,
                    self.screen_w_cm, self.screen_h_cm, self.eye_dist_cm
                )
                self.eye_detected.emit(*eye_cm)
            else:
                self.eye_lost.emit()

            # Build QImage (must .copy() so Qt owns the buffer)
            bytes_per_line = 3 * w
            q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            self.frame_ready.emit(q_img)

        face_mesh.close()
        cap.release()


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
        self._norm_x = 0.5
        self._norm_y = 0.5
        self._has_intersection = False
        self._in_bounds = False

        # Windshield aspect ratio (updated from controls)
        self._ws_aspect = 34.5 / 19.4

    def set_windshield_aspect(self, w_cm, h_cm):
        if h_cm > 0:
            self._ws_aspect = w_cm / h_cm
        self.update()

    def update_glare(self, norm_x, norm_y, in_bounds):
        """Update glare position. norm_x/y in [0,1] range."""
        self._norm_x = norm_x
        self._norm_y = norm_y
        self._has_intersection = True
        self._in_bounds = in_bounds
        self.update()

    def clear_glare(self):
        self._has_intersection = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Dark background
        p.fillRect(self.rect(), QColor("#16213e"))

        # Compute windshield rectangle preserving aspect ratio
        margin = 30
        avail_w = self.width() - 2 * margin
        avail_h = self.height() - 2 * margin
        ws_w = min(avail_w, avail_h * self._ws_aspect)
        ws_h = ws_w / self._ws_aspect
        ws_x = (self.width() - ws_w) / 2
        ws_y = (self.height() - ws_h) / 2

        # Windshield fill
        p.setPen(QPen(QColor("#0f4c75"), 2))
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
        p.drawText(int(ws_x - 28), int(cy + 4), "LEFT")
        p.drawText(int(ws_x + ws_w + 4), int(cy + 4), "RIGHT")

        # Title
        p.setPen(QColor("#bbe1fa"))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(int(ws_x), int(ws_y - 20), "Windshield — Front View")

        # Glare spot
        if self._has_intersection:
            spot_x = ws_x + self._norm_x * ws_w
            spot_y = ws_y + self._norm_y * ws_h

            from PyQt5.QtCore import QPointF
            center = QPointF(spot_x, spot_y)

            if self._in_bounds:
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
        self._ws_h = 19.4
        self._build_windshield(34.5, 19.4)

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

        # ── Light source (orange), in front of the windshield ──
        self._light_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, 120, 40]], dtype=np.float32),
            size=14, color=(1.0, 0.6, 0.0, 1.0), pxMode=True
        )
        self.gl_view.addItem(self._light_scatter)

        # ── Eye point (blue), behind the windshield and above the floor ──
        self._eye_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, -50, 10]], dtype=np.float32),
            size=12, color=(0.3, 0.5, 1.0, 1.0), pxMode=True
        )
        self.gl_view.addItem(self._eye_scatter)
        self._eye_visible = False

        # ── Intersection point (yellow) ──
        self._inter_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, 0, 0]], dtype=np.float32),
            size=16, color=(1.0, 0.95, 0.2, 1.0), pxMode=True
        )
        self.gl_view.addItem(self._inter_scatter)
        self._inter_visible = False

        # ── Ray line (red dashed) ──
        self._ray_line = gl.GLLinePlotItem(
            pos=np.array([[0, -50, 10], [0, 120, 40]], dtype=np.float32),
            color=(1.0, 0.2, 0.2, 0.8), width=2.5, antialias=True
        )
        self.gl_view.addItem(self._ray_line)
        self._ray_visible = False

        # Start with tracking items hidden
        self._hide_tracking()

    def _build_windshield(self, w_cm, h_cm):
        """Create or replace the windshield mesh in the vertical X-Z plane at Y=0."""
        if self._ws_mesh is not None:
            self.gl_view.removeItem(self._ws_mesh)

        hw, hh = w_cm / 2, h_cm / 2
        verts = np.array([
            [-hw, 0, 0],
            [hw, 0, 0],
            [hw, 0, h_cm],
            [-hw, 0, h_cm],
        ], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]])

        colors = np.array([
            [0.0, 0.75, 0.85, 0.25],
            [0.0, 0.75, 0.85, 0.25],
        ], dtype=np.float32)

        self._ws_mesh = gl.GLMeshItem(
            vertexes=verts, faces=faces, faceColors=colors,
            smooth=False, drawEdges=True, edgeColor=(0, 0.9, 1, 0.8)
        )
        self.gl_view.addItem(self._ws_mesh)
        self._ws_w = w_cm
        self._ws_h = h_cm

    def update_windshield(self, w_cm, h_cm):
        if abs(w_cm - self._ws_w) > 0.01 or abs(h_cm - self._ws_h) > 0.01:
            self._build_windshield(w_cm, h_cm)

    def update_light(self, x, y, z):
        self._light_scatter.setData(pos=np.array([[x, y, z]], dtype=np.float32))

    def update_eye(self, x, y, z):
        self._eye_scatter.setData(pos=np.array([[x, y, z]], dtype=np.float32))
        if not self._eye_visible:
            self._eye_visible = True

    def update_intersection(self, ix, iy, iz):
        self._inter_scatter.setData(pos=np.array([[ix, iy, iz]], dtype=np.float32))
        if not self._inter_visible:
            self._inter_visible = True

    def update_ray(self, eye_cm, light_cm):
        pts = np.array([list(eye_cm), list(light_cm)], dtype=np.float32)
        self._ray_line.setData(pos=pts)
        if not self._ray_visible:
            self._ray_visible = True

    def _hide_tracking(self):
        """Move tracking items off-screen when no face detected."""
        offscreen = np.array([[9999, 9999, 9999]], dtype=np.float32)
        self._eye_scatter.setData(pos=offscreen)
        self._inter_scatter.setData(pos=offscreen)
        self._ray_line.setData(pos=np.array([[9999, 9999, 9999], [9999, 9999, 9999]], dtype=np.float32))
        self._eye_visible = False
        self._inter_visible = False
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
            ("light_pos", "Light Source"),
            ("intersection", "Intersection"),
            ("in_bounds", "On Windshield"),
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
        self.spin_ws_h = self._make_spin(1.0, 500.0, 19.4, " cm")

        ws_layout.addRow("Width:", self.spin_ws_w)
        ws_layout.addRow("Height:", self.spin_ws_h)
        layout.addWidget(ws_group)

        # ── Eye Distance ──
        dist_group = QGroupBox("Driver Distance (cm)")
        dist_layout = QFormLayout(dist_group)

        self.spin_eye_dist = self._make_spin(5.0, 500.0, 50.0, " cm")
        dist_layout.addRow("Distance:", self.spin_eye_dist)
        layout.addWidget(dist_group)

        # ── Light Source Position ──
        light_group = QGroupBox("Light Source (cm)")
        light_layout = QFormLayout(light_group)

        self.spin_light_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_light_y = self._make_spin(-1000, 1000, 120.0, " cm")
        self.spin_light_z = self._make_spin(-1000, 5000, 40.0, " cm")

        light_layout.addRow("X:", self.spin_light_x)
        light_layout.addRow("Y:", self.spin_light_y)
        light_layout.addRow("Z:", self.spin_light_z)
        layout.addWidget(light_group)

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

    def get_windshield_dims(self):
        return (self.spin_ws_w.value(), self.spin_ws_h.value())

    def get_eye_distance(self):
        return self.spin_eye_dist.value()


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
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(self.video_widget)
        top_splitter.addWidget(self.windshield_2d)
        top_splitter.setSizes([550, 400])

        # Left column: top row above, 3D below
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(top_splitter)
        left_splitter.addWidget(self.scene_3d)
        left_splitter.setSizes([320, 480])

        # Right sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        sidebar_layout.addWidget(self.readout)
        sidebar_layout.addWidget(self.controls)
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(420)

        # Main splitter: left viewport | right sidebar
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(sidebar)
        main_splitter.setSizes([1050, 350])
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 0)

        self.setCentralWidget(main_splitter)

        # ── Camera thread ──
        self.cap_thread = VideoCaptureThread()

        # ── State ──
        self._last_eye_cm = None
        self._calibration_offset = (0.0, 0.0)  # applied to eye x, y
        self._frame_times = []

        # ── Connect signals ──
        self.cap_thread.frame_ready.connect(self.video_widget.update_frame)
        self.cap_thread.eye_detected.connect(self._on_eye_detected)
        self.cap_thread.eye_lost.connect(self._on_eye_lost)

        self.controls.btn_stream.clicked.connect(self._toggle_stream)
        self.controls.btn_calibrate.clicked.connect(self._on_calibrate)
        self.controls.btn_reset_view.clicked.connect(self._on_reset_3d_view)

        # React to parameter changes
        self.controls.spin_ws_w.valueChanged.connect(self._on_params_changed)
        self.controls.spin_ws_h.valueChanged.connect(self._on_params_changed)
        self.controls.spin_eye_dist.valueChanged.connect(self._on_params_changed)
        self.controls.spin_light_x.valueChanged.connect(self._on_params_changed)
        self.controls.spin_light_y.valueChanged.connect(self._on_params_changed)
        self.controls.spin_light_z.valueChanged.connect(self._on_params_changed)

        # Initial parameter push
        self._on_params_changed()

        # ── FPS timer ──
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)

    # ── Stream control ─────────────────────────────────────────────
    def _toggle_stream(self, checked):
        if checked:
            self.controls.btn_stream.setText("⏹  Stop Stream")
            self._push_config_to_thread()
            self.cap_thread._running = True
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
        self.cap_thread.update_config(
            self.controls.spin_ws_w.value(),
            self.controls.spin_ws_h.value(),
            self.controls.spin_eye_dist.value(),
        )

    # ── Parameter changes ──────────────────────────────────────────
    def _on_params_changed(self):
        ws_w, ws_h = self.controls.get_windshield_dims()
        light = self.controls.get_light_pos()

        # Update 3D scene
        self.scene_3d.update_windshield(ws_w, ws_h)
        self.scene_3d.update_light(*light)

        # Update 2D windshield aspect
        self.windshield_2d.set_windshield_aspect(ws_w, ws_h)

        # Update readout
        self.readout.set_value(
            "light_pos",
            f"X:{light[0]:7.1f}  Y:{light[1]:7.1f}  Z:{light[2]:7.1f}"
        )

        # Push to thread if running
        if self.cap_thread.isRunning():
            self._push_config_to_thread()

        # Recalculate with last known eye position
        if self._last_eye_cm:
            self._process_tracking(self._last_eye_cm)

    # ── Eye tracking callbacks ─────────────────────────────────────
    def _on_eye_detected(self, x, y, z):
        # Apply calibration offset
        adjusted = (x - self._calibration_offset[0],
                    y - self._calibration_offset[1],
                    z)
        self._last_eye_cm = adjusted
        self._frame_times.append(time.time())
        self._process_tracking(adjusted)

    def _process_tracking(self, eye_cm):
        light = self.controls.get_light_pos()
        ws_w, ws_h = self.controls.get_windshield_dims()

        # Update 3D: eye + ray
        self.scene_3d.update_eye(*eye_cm)
        self.scene_3d.update_ray(eye_cm, light)

        # Compute intersection
        intersection = compute_intersection(eye_cm, light)

        # Update readout: eye
        self.readout.set_value(
            "eye_pos",
            f"X:{eye_cm[0]:7.1f}  Y:{eye_cm[1]:7.1f}  Z:{eye_cm[2]:7.1f}",
            "#58a6ff"
        )
        self.readout.set_value("status", "TRACKING ●", "#4caf50")

        if intersection:
            ix, iy, iz = intersection

            # Check if within windshield bounds
            hw, hh = ws_w / 2, ws_h / 2
            in_bounds = (-hw <= ix <= hw) and (0.0 <= iz <= ws_h)

            # Update 3D intersection
            self.scene_3d.update_intersection(ix, iy, iz)

            # Update 2D windshield (convert to 0-1 normalised coords)
            norm_x = (ix + hw) / ws_w
            norm_y = (ws_h - iz) / ws_h  # flip Z: positive up → top of widget
            self.windshield_2d.update_glare(norm_x, norm_y, in_bounds)

            # Update readout
            self.readout.set_value(
                "intersection",
                f"X:{ix:7.1f}  Z:{iz:7.1f}",
                "#ffeb3b" if in_bounds else "#f44336"
            )
            self.readout.set_value(
                "in_bounds",
                "YES ✓" if in_bounds else "NO ✗ (outside)",
                "#4caf50" if in_bounds else "#f44336"
            )
        else:
            self.windshield_2d.clear_glare()
            self.readout.set_value("intersection", "— (parallel ray)", "#666")
            self.readout.set_value("in_bounds", "—", "#666")

    def _on_eye_lost(self):
        self._last_eye_cm = None
        self.scene_3d.hide_tracking()
        self.windshield_2d.clear_glare()
        self.readout.set_value("eye_pos", "— (no face detected)", "#f44336")
        self.readout.set_value("intersection", "—", "#666")
        self.readout.set_value("in_bounds", "—", "#666")
        self.readout.set_value("status", "NO FACE ●", "#f44336")

    # ── Calibration ────────────────────────────────────────────────
    def _on_calibrate(self):
        """Set current eye position as the center reference (0, 0)."""
        if self._last_eye_cm:
            self._calibration_offset = (self._last_eye_cm[0], self._last_eye_cm[1])
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
        self.cap_thread.stop()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # consistent cross-platform look

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
