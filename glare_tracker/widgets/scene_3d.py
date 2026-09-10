"""GPU-accelerated 3D scene widget (PyQtGraph OpenGL).

Manages windshield mesh, eye point, up to 4 light sources, intersection
markers, ray lines, axis labels, camera marker, and a floating settings
overlay — all updated in-place via ``setData()`` for 60+ FPS.
"""

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QGridLayout, QLabel,
    QToolButton, QPushButton, QSlider, QColorDialog,
)

import pyqtgraph.opengl as gl
from pyqtgraph.opengl import GLTextItem


_OFFSCREEN_POINT = np.array([[9999, 9999, 9999]], dtype=np.float32)
_OFFSCREEN_LINE = np.array([[9999, 9999, 9999], [9999, 9999, 9999]], dtype=np.float32)
_MAX_LIGHTS = 4


class Scene3DWidget(QWidget):
    """Wraps a ``GLViewWidget`` and manages all 3D scene objects."""

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
        self._intersection_points: list = []
        self._last_light_positions = None
        self._last_eye_position = None
        self._last_ray_positions = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.gl_view = gl.GLViewWidget()
        self.gl_view.setBackgroundColor(QColor("#0a0a1a"))
        self.gl_view.setCameraPosition(distance=140, elevation=20, azimuth=-45)
        layout.addWidget(self.gl_view)

        self._build_static_scene()
        self._build_dynamic_items()
        self._build_settings_overlay()
        self._hide_tracking()

    # ── static scene elements ───────────────────────────────────────

    def _build_static_scene(self):
        # Grid
        grid = gl.GLGridItem()
        grid.setSize(200, 200, 1)
        grid.setSpacing(10, 10, 10)
        grid.setColor(QColor(255, 255, 255, 30))
        self.gl_view.addItem(grid)

        # Windshield mesh (rebuilt when dimensions change)
        self._ws_mesh = None
        self._ws_w = 34.5
        self._ws_h = 19.5
        self._build_windshield(34.5, 19.5)

        # Axis lines + labels
        axis_len = 50
        for pts, color in [
            (np.array([[0, 0, 0], [axis_len, 0, 0]]), (1, 0.3, 0.3, 0.5)),
            (np.array([[0, 0, 0], [0, axis_len, 0]]), (0.3, 1, 0.3, 0.5)),
            (np.array([[0, 0, 0], [0, 0, axis_len]]), (0.3, 0.3, 1, 0.5)),
        ]:
            self.gl_view.addItem(gl.GLLinePlotItem(pos=pts, color=color, width=1.5, antialias=True))

        for text, pos, color in [
            ("X", (axis_len, 0, 0), (1.0, 0.3, 0.3, 1.0)),
            ("Y", (0, axis_len, 0), (0.3, 1.0, 0.3, 1.0)),
            ("Z", (0, 0, axis_len), (0.3, 0.3, 1.0, 1.0)),
        ]:
            self.gl_view.addItem(GLTextItem(pos=pos, text=text, color=color))

    # ── dynamic tracking items ──────────────────────────────────────

    def _build_dynamic_items(self):
        self._light_scatters = []
        self._light_labels = []
        self._inter_scatters = []
        self._inter_labels = []
        self._ray_lines = []

        for idx in range(_MAX_LIGHTS):
            light_s = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=14, color=(1.0, 0.6, 0.0, 1.0), pxMode=True)
            self.gl_view.addItem(light_s)
            self._light_scatters.append(light_s)

            light_l = GLTextItem(pos=(9999, 9999, 9999), text=f"Light Source {idx + 1}",
                                 color=(1.0, 0.7, 0.2, 1.0))
            self.gl_view.addItem(light_l)
            self._light_labels.append(light_l)

            inter_s = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=22, color=(1.0, 0.95, 0.2, 1.0), pxMode=True)
            self.gl_view.addItem(inter_s)
            self._inter_scatters.append(inter_s)

            inter_l = GLTextItem(pos=(9999, 9999, 9999), text=f"Intersection {idx + 1}",
                                 color=(1.0, 0.95, 0.2, 1.0))
            self.gl_view.addItem(inter_l)
            self._inter_labels.append(inter_l)

            ray = gl.GLLinePlotItem(pos=_OFFSCREEN_LINE, color=(1.0, 0.2, 0.2, 0.8),
                                    width=2.5, antialias=True)
            self.gl_view.addItem(ray)
            self._ray_lines.append(ray)

        # Eye
        self._eye_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, -50, 10]], dtype=np.float32),
            size=12, color=(0.3, 0.5, 1.0, 1.0), pxMode=True)
        self.gl_view.addItem(self._eye_scatter)
        self._eye_label = GLTextItem(pos=(9999, 9999, 9999), text="Driver Eye",
                                     color=(0.4, 0.6, 1.0, 1.0))
        self.gl_view.addItem(self._eye_label)

        # Camera marker
        self._camera_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, 0, 30]], dtype=np.float32),
            size=10, color=(0.8, 0.8, 0.8, 1.0), pxMode=True)
        self.gl_view.addItem(self._camera_scatter)
        self._camera_label = GLTextItem(pos=(0, 0, 30), text="Webcam",
                                        color=(0.8, 0.8, 0.8, 1.0))
        self.gl_view.addItem(self._camera_label)

        self._eye_visible = False
        self._ray_visible = False
        self._active_light_count = 0

    # ── windshield mesh ─────────────────────────────────────────────

    def _build_windshield(self, w_cm, h_cm):
        hw = w_cm / 2
        verts = np.array([[-hw, 0, 0], [hw, 0, 0], [hw, 0, h_cm], [-hw, 0, h_cm]], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]])

        c = self._scene_colors["windshield"]
        colors = np.array([[c.redF(), c.greenF(), c.blueF(), 0.25]] * 2, dtype=np.float32)

        kwargs = dict(vertexes=verts, faces=faces, faceColors=colors, smooth=False,
                      drawEdges=True, edgeColor=(c.redF(), c.greenF(), c.blueF(), 0.8))
        if self._ws_mesh is None:
            self._ws_mesh = gl.GLMeshItem(**kwargs)
            self.gl_view.addItem(self._ws_mesh)
        else:
            self._ws_mesh.setMeshData(**kwargs)
        self._ws_w = w_cm
        self._ws_h = h_cm
        if hasattr(self, "_inter_scatters"):
            self._restore_intersections()

    def update_windshield(self, w_cm, h_cm):
        if abs(w_cm - self._ws_w) > 0.01 or abs(h_cm - self._ws_h) > 0.01:
            self._build_windshield(w_cm, h_cm)

    # ── public update methods ───────────────────────────────────────

    def update_light(self, x, y, z):
        self.update_lights([(x, y, z)])

    def update_lights(self, light_positions):
        positions = tuple(tuple(p) for p in light_positions[:_MAX_LIGHTS])
        if positions == self._last_light_positions:
            return
        self._last_light_positions = positions
        self._active_light_count = min(_MAX_LIGHTS, len(light_positions))
        for i in range(_MAX_LIGHTS):
            if i < self._active_light_count:
                pos = np.array([light_positions[i]], dtype=np.float32)
                self._light_scatters[i].setData(pos=pos)
                self._light_labels[i].setData(pos=light_positions[i])
            else:
                self._light_scatters[i].setData(pos=_OFFSCREEN_POINT)
                self._light_labels[i].setData(pos=(9999, 9999, 9999))

    def update_eye(self, x, y, z):
        position = (x, y, z)
        if position == self._last_eye_position:
            return
        self._last_eye_position = position
        self._eye_scatter.setData(pos=np.array([[x, y, z]], dtype=np.float32))
        self._eye_label.setData(pos=position)
        self._eye_visible = True

    def update_camera(self, x, y, z):
        self._camera_scatter.setData(pos=np.array([[x, y, z]], dtype=np.float32))
        self._camera_label.setData(pos=(x, y, z))

    def update_intersection(self, ix, iy, iz):
        self.update_intersections([(ix, iy, iz)])

    def update_intersections(self, intersections):
        self._intersection_points = list(intersections[:_MAX_LIGHTS])
        self._restore_intersections()

    def _restore_intersections(self):
        for i in range(_MAX_LIGHTS):
            if i < len(self._intersection_points):
                pt = self._intersection_points[i]
                display = (pt[0], -0.6, pt[2])
                self._inter_scatters[i].setData(pos=np.array([display], dtype=np.float32))
                self._inter_labels[i].setData(pos=display)
            else:
                self._inter_scatters[i].setData(pos=_OFFSCREEN_POINT)
                self._inter_labels[i].setData(pos=(9999, 9999, 9999))

    def update_ray(self, eye_cm, light_cm):
        self.update_rays(eye_cm, [light_cm])

    def update_rays(self, eye_cm, light_positions):
        ray_key = (tuple(eye_cm), *(tuple(p) for p in light_positions[:_MAX_LIGHTS]))
        if ray_key == self._last_ray_positions:
            return
        self._last_ray_positions = ray_key
        for i in range(_MAX_LIGHTS):
            if i < len(light_positions):
                pts = np.array([list(eye_cm), list(light_positions[i])], dtype=np.float32)
                self._ray_lines[i].setData(pos=pts)
            else:
                self._ray_lines[i].setData(pos=_OFFSCREEN_LINE)
        if light_positions:
            self._ray_visible = True

    def hide_tracking(self):
        self._hide_tracking()

    def _hide_tracking(self):
        self._intersection_points = []
        self._last_eye_position = None
        self._last_ray_positions = None
        self._eye_scatter.setData(pos=_OFFSCREEN_POINT)
        self._eye_label.setData(pos=(9999, 9999, 9999))
        for s, l in zip(self._inter_scatters, self._inter_labels):
            s.setData(pos=_OFFSCREEN_POINT)
            l.setData(pos=(9999, 9999, 9999))
        for r in self._ray_lines:
            r.setData(pos=_OFFSCREEN_LINE)
        self._eye_visible = False
        self._ray_visible = False

    # ── settings overlay ────────────────────────────────────────────

    def _build_settings_overlay(self):
        self.settings_button = QToolButton(self)
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("3D view settings")
        self.settings_button.setFixedSize(36, 36)
        self.settings_button.clicked.connect(self._toggle_settings)

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
        panel = QGridLayout(self.settings_panel)
        panel.setContentsMargins(8, 8, 8, 8)
        panel.setSpacing(6)
        panel.addWidget(QLabel("3D view"), 0, 0, 1, 2)

        self._add_color_row(panel, 1, "Windshield", "windshield")
        self._add_color_row(panel, 2, "Driver eye", "eye")
        self._add_color_row(panel, 3, "Light source", "light")
        self._add_label_size_row(panel, 4, "Eye label size", "eye")
        self._add_label_size_row(panel, 5, "Light label size", "light")

        self.eye_toggle = QToolButton()
        self.eye_toggle.setText("👁  Eye points")
        self.eye_toggle.setCheckable(True)
        self.eye_toggle.setChecked(True)
        self.eye_toggle.clicked.connect(self._toggle_eye_visibility)
        panel.addWidget(self.eye_toggle, 6, 0, 1, 2)

        self.light_toggle = QToolButton()
        self.light_toggle.setText("☀  Light points")
        self.light_toggle.setCheckable(True)
        self.light_toggle.setChecked(True)
        self.light_toggle.clicked.connect(self._toggle_light_visibility)
        panel.addWidget(self.light_toggle, 7, 0, 1, 2)

        self.settings_panel.adjustSize()
        self.settings_panel.hide()

    def _add_color_row(self, layout, row, label, key):
        layout.addWidget(QLabel(label), row, 0)
        btn = QPushButton()
        btn.setToolTip(f"Change {label.lower()} color")
        btn.clicked.connect(lambda: self._pick_color(key))
        self._style_color_button(btn, self._scene_colors[key])
        setattr(self, f"_{key}_color_button", btn)
        layout.addWidget(btn, row, 1)

    def _add_label_size_row(self, layout, row, label, key):
        layout.addWidget(QLabel(label), row, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(8, 32)
        slider.setValue(self._eye_label_size if key == "eye" else self._light_label_size)
        slider.valueChanged.connect(lambda v: self._set_label_size(key, v))
        layout.addWidget(slider, row, 1)

    def _set_label_size(self, key, size):
        font = QFont("Segoe UI", size)
        if key == "eye":
            self._eye_label_size = size
            self._eye_label.setData(font=font)
        else:
            self._light_label_size = size
            for lbl in self._light_labels:
                lbl.setData(font=font)

    @staticmethod
    def _style_color_button(button, color):
        button.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #ffffff; "
            "border-radius: 3px; min-width: 34px; min-height: 22px;")

    def _pick_color(self, key):
        color = QColorDialog.getColor(self._scene_colors[key], self, "Choose 3D color")
        if color.isValid():
            self._scene_colors[key] = color
            self._style_color_button(getattr(self, f"_{key}_color_button"), color)
            self._apply_colors()

    def _apply_colors(self):
        self._build_windshield(self._ws_w, self._ws_h)
        eye_c = self._scene_colors["eye"]
        light_c = self._scene_colors["light"]
        for s in self._light_scatters:
            s.setData(color=light_c)
        for l in self._light_labels:
            l.setData(color=light_c)
        self._eye_scatter.setData(color=eye_c)
        self._eye_label.setData(color=eye_c)

    def _toggle_settings(self):
        self.settings_panel.setVisible(not self.settings_panel.isVisible())
        self._position_settings()

    def _toggle_eye_visibility(self, visible):
        self._eye_points_visible = visible
        self._eye_scatter.setVisible(visible)
        self._eye_label.setVisible(visible)

    def _toggle_light_visibility(self, visible):
        self._light_points_visible = visible
        for s, l in zip(self._light_scatters, self._light_labels):
            s.setVisible(visible)
            l.setVisible(visible)

    def _position_settings(self):
        margin = 10
        self.settings_button.move(self.width() - self.settings_button.width() - margin, margin)
        self.settings_button.raise_()
        if self.settings_panel.isVisible():
            self.settings_panel.adjustSize()
            self.settings_panel.move(
                self.width() - self.settings_panel.width() - margin,
                self.settings_button.height() + margin * 2)
            self.settings_panel.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_settings()
