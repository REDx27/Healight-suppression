"""GPU-accelerated 3D scene widget (PyQtGraph OpenGL).

Manages windshield mesh, two eye points, up to 8 light sources, intersection
markers, ray lines, axis labels, camera marker, and a floating settings
overlay — all updated in-place via ``setData()`` for 60+ FPS.
"""

import numpy as np

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QGridLayout, QLabel,
    QToolButton, QPushButton, QSlider, QColorDialog,
)

import pyqtgraph.opengl as gl
from pyqtgraph.opengl import GLTextItem

from glare_tracker.widgets.icons import ICON_SIZE, IconFactory


_OFFSCREEN_POINT = np.array([[9999, 9999, 9999]], dtype=np.float32)
_OFFSCREEN_LINE = np.array([[9999, 9999, 9999], [9999, 9999, 9999]], dtype=np.float32)
_MAX_LIGHTS = 8
_MAX_EYES = 2
_MAX_INTERSECTIONS = _MAX_LIGHTS * _MAX_EYES


class Scene3DWidget(QWidget):
    """Wraps a ``GLViewWidget`` and manages all 3D scene objects."""

    scene_theme_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_colors = {
            "windshield": QColor("#22b8cf"),
            "eye": QColor("#60a5fa"),
            "light": QColor("#fbbf24"),
        }
        self._eye_points_visible = True
        self._light_points_visible = True
        self._eye_label_size = 16
        self._light_label_size = 16
        self._intersection_points: list = []
        self._last_light_positions = None
        self._last_eye_positions = None
        self._last_ray_positions = None
        self._light_scene = False
        self._grid_visible = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.gl_view = gl.GLViewWidget()
        self.gl_view.setBackgroundColor(QColor("#050810"))
        self.gl_view.setCameraPosition(distance=145, elevation=22, azimuth=-45)
        layout.addWidget(self.gl_view)

        self._build_static_scene()
        self._build_dynamic_items()
        self._build_settings_overlay()
        self._build_legend_overlay()
        self._apply_scene_theme()
        self._hide_tracking()

    # ── static scene elements ───────────────────────────────────────

    def _build_static_scene(self):
        # Build non-overlapping minor/major segments. Two GLGridItems draw the
        # major lines twice and produce false-looking parallel bands at shallow
        # view angles, so the divisions are generated explicitly instead.
        self._minor_grid = gl.GLLinePlotItem(
            pos=self._grid_segments(240, 10, exclude_multiple=40),
            color=(0.27, 0.38, 0.50, 0.15), width=1.0,
            antialias=True, mode="lines")
        self.gl_view.addItem(self._minor_grid)
        self._major_grid = gl.GLLinePlotItem(
            pos=self._grid_segments(240, 40),
            color=(0.13, 0.56, 0.66, 0.24), width=1.2,
            antialias=True, mode="lines")
        self.gl_view.addItem(self._major_grid)

        # Windshield mesh (rebuilt when dimensions change)
        self._ws_mesh = None
        self._ws_frame = None
        self._ws_w = 34.5
        self._ws_h = 19.5
        self._build_windshield(34.5, 19.5)

        # Axis lines + labels
        axis_len = 50
        self._axis_lines = []
        for pts, color in [
            (np.array([[0, 0, 0], [axis_len, 0, 0]]), (0.97, 0.44, 0.44, 0.55)),
            (np.array([[0, 0, 0], [0, axis_len, 0]]), (0.20, 0.83, 0.60, 0.55)),
            (np.array([[0, 0, 0], [0, 0, axis_len]]), (0.38, 0.65, 0.98, 0.55)),
        ]:
            line = gl.GLLinePlotItem(pos=pts, color=color, width=1.5, antialias=True)
            self.gl_view.addItem(line)
            self._axis_lines.append(line)

        self._axis_labels = []
        for text, pos, color in [
            ("X", (axis_len, 0, 0), (1.0, 0.3, 0.3, 1.0)),
            ("Y", (0, axis_len, 0), (0.3, 1.0, 0.3, 1.0)),
            ("Z", (0, 0, axis_len), (0.3, 0.3, 1.0, 1.0)),
        ]:
            label = GLTextItem(pos=pos, text=text, color=color)
            self.gl_view.addItem(label)
            self._axis_labels.append(label)

    @staticmethod
    def _grid_segments(size, spacing, exclude_multiple=None):
        """Return XY line pairs without duplicate major or origin lines."""

        half = float(size) / 2.0
        values = np.arange(-half, half + spacing * 0.5, spacing, dtype=float)
        segments = []
        for value in values:
            if abs(value) < 1e-9:
                continue
            if (exclude_multiple is not None
                    and abs(value % exclude_multiple) < 1e-9):
                continue
            segments.extend((
                (-half, value, 0.0), (half, value, 0.0),
                (value, -half, 0.0), (value, half, 0.0),
            ))
        return np.asarray(segments, dtype=np.float32)

    # ── dynamic tracking items ──────────────────────────────────────

    def _build_dynamic_items(self):
        self._light_scatters = []
        self._light_glows = []
        self._light_labels = []
        self._inter_scatters = []
        self._inter_glows = []
        self._inter_labels = []
        self._ray_lines = []

        for idx in range(_MAX_LIGHTS):
            light_g = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=34, color=(1.0, 0.65, 0.12, 0.16), pxMode=True)
            self.gl_view.addItem(light_g)
            self._light_glows.append(light_g)

            light_s = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=11, color=(1.0, 0.75, 0.18, 1.0), pxMode=True)
            self.gl_view.addItem(light_s)
            self._light_scatters.append(light_s)

            light_l = GLTextItem(pos=(9999, 9999, 9999), text=f"Light Source {idx + 1}",
                                 color=(1.0, 0.7, 0.2, 1.0))
            self.gl_view.addItem(light_l)
            self._light_labels.append(light_l)

        for idx in range(_MAX_INTERSECTIONS):
            inter_g = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=36, color=(0.98, 0.45, 0.12, 0.18), pxMode=True)
            self.gl_view.addItem(inter_g)
            self._inter_glows.append(inter_g)

            inter_s = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=13, color=(1.0, 0.82, 0.25, 1.0), pxMode=True)
            self.gl_view.addItem(inter_s)
            self._inter_scatters.append(inter_s)

            inter_l = GLTextItem(pos=(9999, 9999, 9999), text=f"Intersection {idx + 1}",
                                 color=(1.0, 0.95, 0.2, 1.0))
            self.gl_view.addItem(inter_l)
            self._inter_labels.append(inter_l)

            ray = gl.GLLinePlotItem(pos=_OFFSCREEN_LINE, color=(0.97, 0.35, 0.28, 0.68),
                                    width=1.7, antialias=True)
            self.gl_view.addItem(ray)
            self._ray_lines.append(ray)

        # Independent eye markers preserve the separation caused by head roll.
        self._eye_glows = []
        self._eye_scatters = []
        self._eye_labels = []
        for idx in range(_MAX_EYES):
            eye_glow = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=30,
                color=(0.38, 0.65, 0.98, 0.16), pxMode=True)
            self.gl_view.addItem(eye_glow)
            self._eye_glows.append(eye_glow)

            eye_scatter = gl.GLScatterPlotItem(
                pos=_OFFSCREEN_POINT, size=10,
                color=(0.38, 0.65, 0.98, 1.0), pxMode=True)
            self.gl_view.addItem(eye_scatter)
            self._eye_scatters.append(eye_scatter)

            eye_label = GLTextItem(
                pos=(9999, 9999, 9999), text=f"Eye {idx + 1}",
                color=(0.4, 0.6, 1.0, 1.0))
            self.gl_view.addItem(eye_label)
            self._eye_labels.append(eye_label)

        # Camera marker
        self._camera_glow = gl.GLScatterPlotItem(
            pos=np.array([[0, 0, 30]], dtype=np.float32),
            size=24, color=(0.58, 0.68, 0.78, 0.12), pxMode=True)
        self.gl_view.addItem(self._camera_glow)
        self._camera_scatter = gl.GLScatterPlotItem(
            pos=np.array([[0, 0, 30]], dtype=np.float32),
            size=8, color=(0.70, 0.79, 0.88, 1.0), pxMode=True)
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
        colors = np.array([[c.redF(), c.greenF(), c.blueF(), 0.16]] * 2, dtype=np.float32)

        kwargs = dict(vertexes=verts, faces=faces, faceColors=colors, smooth=False,
                      drawEdges=False)
        if self._ws_mesh is None:
            self._ws_mesh = gl.GLMeshItem(**kwargs, glOptions="translucent")
            self.gl_view.addItem(self._ws_mesh)
        else:
            self._ws_mesh.setMeshData(**kwargs)

        frame = np.array([
            [-hw, -0.18, 0], [hw, -0.18, 0], [hw, -0.18, h_cm],
            [-hw, -0.18, h_cm], [-hw, -0.18, 0],
        ], dtype=np.float32)
        frame_color = (c.redF(), c.greenF(), c.blueF(), 0.92)
        if self._ws_frame is None:
            self._ws_frame = gl.GLLinePlotItem(
                pos=frame, color=frame_color, width=2.2, antialias=True)
            self.gl_view.addItem(self._ws_frame)
        else:
            self._ws_frame.setData(pos=frame, color=frame_color)
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
                self._light_glows[i].setData(pos=pos)
                self._light_scatters[i].setData(pos=pos)
                self._light_labels[i].setData(pos=light_positions[i])
            else:
                self._light_glows[i].setData(pos=_OFFSCREEN_POINT)
                self._light_scatters[i].setData(pos=_OFFSCREEN_POINT)
                self._light_labels[i].setData(pos=(9999, 9999, 9999))

    def update_eye(self, x, y, z):
        self.update_eyes(((x, y, z),))

    def update_eyes(self, eye_positions):
        positions = tuple(tuple(position) for position in eye_positions[:_MAX_EYES])
        if positions == self._last_eye_positions:
            return
        self._last_eye_positions = positions
        dual = len(positions) > 1
        for idx in range(_MAX_EYES):
            if idx < len(positions):
                position = positions[idx]
                pos = np.array([position], dtype=np.float32)
                self._eye_glows[idx].setData(pos=pos)
                self._eye_scatters[idx].setData(pos=pos)
                label = f"Eye {idx + 1}" if dual else "Driver Eye"
                self._eye_labels[idx].setData(pos=position, text=label)
            else:
                self._eye_glows[idx].setData(pos=_OFFSCREEN_POINT)
                self._eye_scatters[idx].setData(pos=_OFFSCREEN_POINT)
                self._eye_labels[idx].setData(pos=(9999, 9999, 9999))
        self._eye_visible = bool(positions)

    def update_camera(self, x, y, z):
        pos = np.array([[x, y, z]], dtype=np.float32)
        self._camera_glow.setData(pos=pos)
        self._camera_scatter.setData(pos=pos)
        self._camera_label.setData(pos=(x, y, z))

    def update_intersection(self, ix, iy, iz):
        self.update_intersections([(ix, iy, iz)])

    def update_intersections(self, intersections):
        self._intersection_points = list(intersections[:_MAX_INTERSECTIONS])
        self._restore_intersections()

    def _restore_intersections(self):
        for i in range(_MAX_INTERSECTIONS):
            if i < len(self._intersection_points):
                pt = self._intersection_points[i]
                display = (pt[0], -0.6, pt[2])
                pos = np.array([display], dtype=np.float32)
                self._inter_glows[i].setData(pos=pos)
                self._inter_scatters[i].setData(pos=pos)
                self._inter_labels[i].setData(pos=display)
            else:
                self._inter_glows[i].setData(pos=_OFFSCREEN_POINT)
                self._inter_scatters[i].setData(pos=_OFFSCREEN_POINT)
                self._inter_labels[i].setData(pos=(9999, 9999, 9999))

    def update_ray(self, eye_cm, light_cm):
        self.update_rays(eye_cm, [light_cm])

    def update_rays(self, eye_cm, light_positions):
        self.update_eye_rays((eye_cm,), light_positions)

    def update_eye_rays(self, eye_positions, light_positions):
        eyes = tuple(tuple(eye) for eye in eye_positions[:_MAX_EYES])
        lights = tuple(tuple(light) for light in light_positions[:_MAX_LIGHTS])
        ray_key = (eyes, lights)
        if ray_key == self._last_ray_positions:
            return
        self._last_ray_positions = ray_key
        pairs = [(eye, light) for light in lights for eye in eyes]
        for i in range(_MAX_INTERSECTIONS):
            if i < len(pairs):
                eye, light = pairs[i]
                pts = np.array([eye, light], dtype=np.float32)
                self._ray_lines[i].setData(pos=pts)
            else:
                self._ray_lines[i].setData(pos=_OFFSCREEN_LINE)
        self._ray_visible = bool(pairs)

    def hide_tracking(self):
        self._hide_tracking()

    def _hide_tracking(self):
        self._intersection_points = []
        self._last_eye_positions = None
        self._last_ray_positions = None
        for glow, scatter, label in zip(
                self._eye_glows, self._eye_scatters, self._eye_labels):
            glow.setData(pos=_OFFSCREEN_POINT)
            scatter.setData(pos=_OFFSCREEN_POINT)
            label.setData(pos=(9999, 9999, 9999))
        for g, s, l in zip(self._inter_glows, self._inter_scatters, self._inter_labels):
            g.setData(pos=_OFFSCREEN_POINT)
            s.setData(pos=_OFFSCREEN_POINT)
            l.setData(pos=(9999, 9999, 9999))
        for r in self._ray_lines:
            r.setData(pos=_OFFSCREEN_LINE)
        self._eye_visible = False
        self._ray_visible = False

    # ── settings overlay ────────────────────────────────────────────

    def _build_settings_overlay(self):
        self.settings_button = QToolButton(self)
        self.settings_button.setObjectName("sceneToolButton")
        self.settings_button.setIcon(IconFactory.icon("settings", "#c4b5fd"))
        self.settings_button.setIconSize(ICON_SIZE)
        self.settings_button.setToolTip("3D view settings")
        self.settings_button.setFixedSize(36, 36)
        self.settings_button.clicked.connect(self._toggle_settings)

        self.theme_button = QToolButton(self)
        self.theme_button.setObjectName("sceneToolButton")
        self.theme_button.setIconSize(ICON_SIZE)
        self.theme_button.setToolTip("Use a light gray 3D canvas")
        self.theme_button.setFixedSize(36, 36)
        self.theme_button.setCheckable(True)
        self.theme_button.toggled.connect(self._toggle_scene_theme)

        self.grid_button = QToolButton(self)
        self.grid_button.setObjectName("sceneToolButton")
        self.grid_button.setIcon(IconFactory.icon("grid", "#78b7ff"))
        self.grid_button.setIconSize(ICON_SIZE)
        self.grid_button.setToolTip("Hide ground grid")
        self.grid_button.setFixedSize(36, 36)
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(True)
        self.grid_button.toggled.connect(self._toggle_grid)

        self.settings_panel = QFrame(self)
        self.settings_panel.setObjectName("sceneSettingsPanel")
        self.settings_panel.setStyleSheet(
            "QFrame#sceneSettingsPanel { background: rgba(17, 18, 23, 245); "
            "border: 1px solid #5d458c; border-radius: 8px; }"
            "QLabel { color: #b5bac4; background: transparent; }"
            "QToolButton { color: #b5bac4; background: #1a1c23; border: 1px solid #343943; "
            "border-radius: 5px; padding: 4px; }"
            "QToolButton:checked { background: #251d35; border-color: #8b5cf6; color: #c4b5fd; }"
            "QPushButton { border: 1px solid #414957; border-radius: 4px; min-width: 34px; "
            "min-height: 22px; }"
        )
        panel = QGridLayout(self.settings_panel)
        panel.setContentsMargins(8, 8, 8, 8)
        panel.setSpacing(6)
        panel.addWidget(QLabel("SCENE APPEARANCE"), 0, 0, 1, 2)

        self._add_color_row(panel, 1, "Windshield", "windshield")
        self._add_color_row(panel, 2, "Driver eye", "eye")
        self._add_color_row(panel, 3, "Light source", "light")
        self._add_label_size_row(panel, 4, "Eye label size", "eye")
        self._add_label_size_row(panel, 5, "Light label size", "light")

        self.eye_toggle = QToolButton()
        self.eye_toggle.setIcon(IconFactory.icon("eye"))
        self.eye_toggle.setIconSize(ICON_SIZE)
        self.eye_toggle.setText("Eye markers")
        self.eye_toggle.setCheckable(True)
        self.eye_toggle.setChecked(True)
        self.eye_toggle.clicked.connect(self._toggle_eye_visibility)
        panel.addWidget(self.eye_toggle, 6, 0, 1, 2)

        self.light_toggle = QToolButton()
        self.light_toggle.setIcon(IconFactory.icon("light"))
        self.light_toggle.setIconSize(ICON_SIZE)
        self.light_toggle.setText("Light markers")
        self.light_toggle.setCheckable(True)
        self.light_toggle.setChecked(True)
        self.light_toggle.clicked.connect(self._toggle_light_visibility)
        panel.addWidget(self.light_toggle, 7, 0, 1, 2)

        self.settings_panel.adjustSize()
        self.settings_panel.hide()

    def _build_legend_overlay(self):
        self.legend_panel = QFrame(self)
        self.legend_panel.setObjectName("sceneLegend")
        self.legend_panel.setStyleSheet(
            "QFrame#sceneLegend { background: rgba(12, 13, 17, 220); "
            "border: 1px solid #30353e; border-radius: 7px; }"
            "QLabel { color: #929aa7; background: transparent; font-size: 8pt; }"
        )
        row = QGridLayout(self.legend_panel)
        row.setContentsMargins(9, 6, 9, 6)
        row.setHorizontalSpacing(10)
        for column, (color, text) in enumerate([
            ("#60a5fa", "DRIVER EYE"),
            ("#fbbf24", "LIGHT SOURCE"),
            ("#fb923c", "INTERSECTION"),
            ("#22b8cf", "WINDSHIELD"),
        ]):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; background: transparent;")
            row.addWidget(dot, 0, column * 2)
            row.addWidget(QLabel(text), 0, column * 2 + 1)
        self.legend_panel.adjustSize()
        self.legend_panel.show()
        self._position_settings()

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
            for label in self._eye_labels:
                label.setData(font=font)
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
        light_glow = QColor(light_c)
        light_glow.setAlpha(42)
        for g, s in zip(self._light_glows, self._light_scatters):
            g.setData(color=light_glow)
            s.setData(color=light_c)
        for l in self._light_labels:
            l.setData(color=light_c)
        eye_glow = QColor(eye_c)
        eye_glow.setAlpha(42)
        for glow, scatter, label in zip(
                self._eye_glows, self._eye_scatters, self._eye_labels):
            glow.setData(color=eye_glow)
            scatter.setData(color=eye_c)
            label.setData(color=eye_c)

    def _toggle_settings(self):
        self.settings_panel.setVisible(not self.settings_panel.isVisible())
        self._position_settings()

    def _toggle_scene_theme(self, light: bool):
        self._light_scene = light
        self._apply_scene_theme()
        self.scene_theme_changed.emit(light)

    def _toggle_grid(self, visible: bool):
        self._grid_visible = bool(visible)
        self._minor_grid.setVisible(self._grid_visible)
        self._major_grid.setVisible(self._grid_visible)
        self.grid_button.setToolTip(
            "Hide ground grid" if self._grid_visible else "Show ground grid")

    def _apply_scene_theme(self):
        """Keep the original dark scene and provide a high-contrast gray variant."""
        if self._light_scene:
            self.gl_view.setBackgroundColor(QColor("#c3c9cf"))
            self._minor_grid.setData(color=(0.22, 0.27, 0.31, 0.24))
            self._major_grid.setData(color=(0.0, 0.38, 0.49, 0.36))
            axis_colors = [
                (0.72, 0.18, 0.18, 0.76),
                (0.08, 0.48, 0.22, 0.76),
                (0.10, 0.32, 0.72, 0.76),
            ]
            label_colors = [
                (0.62, 0.10, 0.10, 1.0),
                (0.04, 0.38, 0.16, 1.0),
                (0.06, 0.25, 0.62, 1.0),
            ]
            self._set_tracking_colors(
                eye=(0.08, 0.32, 0.72, 1.0),
                light=(0.76, 0.38, 0.0, 1.0),
                intersection=(0.76, 0.18, 0.02, 1.0),
                ray=(0.72, 0.08, 0.08, 0.82),
                additive=False,
            )
            self.legend_panel.setStyleSheet(
                "QFrame#sceneLegend { background: rgba(218, 223, 227, 240); "
                "border: 1px solid #71808b; border-radius: 7px; }"
                "QLabel { color: #2f3d46; background: transparent; font-size: 8pt; }"
            )
            icon_color = "#245d94"
            self.theme_button.setIcon(IconFactory.icon("moon", icon_color))
            self.theme_button.setToolTip("Use the original dark 3D canvas")
        else:
            # Exact scene palette present at the start of today's work.
            self.gl_view.setBackgroundColor(QColor("#050810"))
            self._minor_grid.setData(color=(0.27, 0.38, 0.50, 0.15))
            self._major_grid.setData(color=(0.13, 0.56, 0.66, 0.24))
            axis_colors = [
                (0.97, 0.44, 0.44, 0.55),
                (0.20, 0.83, 0.60, 0.55),
                (0.38, 0.65, 0.98, 0.55),
            ]
            label_colors = [
                (1.0, 0.3, 0.3, 1.0),
                (0.3, 1.0, 0.3, 1.0),
                (0.3, 0.3, 1.0, 1.0),
            ]
            self._set_tracking_colors(
                eye=(0.38, 0.65, 0.98, 1.0),
                light=(1.0, 0.75, 0.18, 1.0),
                intersection=(1.0, 0.82, 0.25, 1.0),
                ray=(0.97, 0.35, 0.28, 0.68),
                additive=True,
            )
            self.legend_panel.setStyleSheet(
                "QFrame#sceneLegend { background: rgba(12, 13, 17, 220); "
                "border: 1px solid #30353e; border-radius: 7px; }"
                "QLabel { color: #929aa7; background: transparent; font-size: 8pt; }"
            )
            icon_color = "#78b7ff"
            self.theme_button.setIcon(IconFactory.icon("sun", icon_color))
            self.theme_button.setToolTip("Use a light gray 3D canvas")

        self.settings_button.setIcon(IconFactory.icon("settings", icon_color))
        self.grid_button.setIcon(IconFactory.icon("grid", icon_color))
        for line, color in zip(self._axis_lines, axis_colors):
            line.setData(color=color)
        for label, color in zip(self._axis_labels, label_colors):
            label.setData(color=color)

    def _set_tracking_colors(self, eye, light, intersection, ray, additive):
        option = "additive" if additive else "translucent"
        for glow, core, label in zip(
                self._light_glows, self._light_scatters, self._light_labels):
            glow.setGLOptions(option)
            core.setGLOptions(option)
            glow_color = (*light[:3], 0.16 if additive else 0.18)
            glow.setData(color=glow_color)
            core.setData(color=light)
            label.setData(color=light)
        for glow, core, label in zip(
                self._inter_glows, self._inter_scatters, self._inter_labels):
            glow.setGLOptions(option)
            core.setGLOptions(option)
            glow_color = (*intersection[:3], 0.18 if additive else 0.22)
            glow.setData(color=glow_color)
            core.setData(color=intersection)
            label.setData(color=intersection)
        for glow, scatter, label in zip(
                self._eye_glows, self._eye_scatters, self._eye_labels):
            glow.setGLOptions(option)
            scatter.setGLOptions(option)
            glow.setData(color=(*eye[:3], 0.16 if additive else 0.18))
            scatter.setData(color=eye)
            label.setData(color=eye)
        for line in self._ray_lines:
            line.setData(color=ray)

    def _toggle_eye_visibility(self, visible):
        self._eye_points_visible = visible
        for glow, scatter, label in zip(
                self._eye_glows, self._eye_scatters, self._eye_labels):
            glow.setVisible(visible)
            scatter.setVisible(visible)
            label.setVisible(visible)

    def _toggle_light_visibility(self, visible):
        self._light_points_visible = visible
        for g, s, l in zip(self._light_glows, self._light_scatters, self._light_labels):
            g.setVisible(visible)
            s.setVisible(visible)
            l.setVisible(visible)

    def _position_settings(self):
        margin = 10
        self.settings_button.move(self.width() - self.settings_button.width() - margin, margin)
        self.theme_button.move(
            self.width() - self.settings_button.width() - self.theme_button.width()
            - margin * 2, margin)
        self.grid_button.move(
            self.width() - self.settings_button.width() - self.theme_button.width()
            - self.grid_button.width() - margin * 3, margin)
        self.settings_button.raise_()
        self.theme_button.raise_()
        self.grid_button.raise_()
        if self.settings_panel.isVisible():
            self.settings_panel.adjustSize()
            self.settings_panel.move(
                self.width() - self.settings_panel.width() - margin,
                self.settings_button.height() + margin * 2)
            self.settings_panel.raise_()
        if hasattr(self, "legend_panel"):
            self.legend_panel.adjustSize()
            self.legend_panel.move(
                margin, self.height() - self.legend_panel.height() - margin)
            self.legend_panel.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_settings()
