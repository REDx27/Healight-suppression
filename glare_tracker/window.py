"""Main application window — layout and signal wiring only.

All tracking logic lives in :class:`~glare_tracker.tracking.TrackingController`.
"""

import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QScrollArea,
)

from glare_tracker.camera import VideoCaptureThread
from glare_tracker.config import TrackingConfig
from glare_tracker.styles import DARK_STYLESHEET
from glare_tracker.tracking import TrackingController
from glare_tracker.widgets import (
    VideoWidget, Windshield2DWidget, Scene3DWidget, ReadoutPanel, ControlsPanel,
)


class MainWindow(QMainWindow):
    """Assembles all panels and wires signals to the tracking controller."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Windshield Glare Tracking System")
        self.setWindowIcon(self._application_icon())
        self.resize(1400, 850)
        self.setStyleSheet(DARK_STYLESHEET)

        # ── widgets ──
        self.video_widget = VideoWidget()
        self.windshield_2d = Windshield2DWidget()
        self.scene_3d = Scene3DWidget()
        self.readout = ReadoutPanel()
        self.controls = ControlsPanel()

        # ── tracking controller ──
        self.tracker = TrackingController(
            self.scene_3d, self.windshield_2d, self.readout, self.controls,
        )

        # ── camera thread ──
        self.cap_thread = VideoCaptureThread()

        # ── layout ──
        self._build_layout()

        # ── signal wiring ──
        self._connect_signals()

        # ── timers ──
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self.tracker.update_fps)
        self._fps_timer.start(1000)

        self._movement_timer = QTimer(self)
        self._movement_timer.setInterval(50)
        self._movement_timer.timeout.connect(self.tracker.advance_movement)

        # Push initial parameters
        self.tracker.on_params_changed()

    # ── layout ──────────────────────────────────────────────────────

    def _build_layout(self):
        # Top row: Camera | 2D Windshield
        self.top_splitter = QSplitter(Qt.Horizontal)
        self.top_splitter.addWidget(self.video_widget)
        self.top_splitter.addWidget(self.windshield_2d)
        self.top_splitter.setSizes([550, 400])
        self.top_splitter.setStretchFactor(0, 1)
        self.top_splitter.setStretchFactor(1, 1)

        # Left: top row + 3D below
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.addWidget(self.top_splitter)
        self.left_splitter.addWidget(self.scene_3d)
        self.left_splitter.setSizes([320, 480])
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 1)

        # Scrollable sidebar
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

        # Main: viewport | sidebar
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(sidebar)
        self.main_splitter.setSizes([1050, 350])
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(12, 12, 12, 12)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.main_splitter)
        self.setCentralWidget(central)

    # ── signal wiring ───────────────────────────────────────────────

    def _connect_signals(self):
        # Camera → display + tracker
        self.cap_thread.frame_ready.connect(self.video_widget.update_frame)
        self.cap_thread.eye_detected.connect(self.tracker.on_eye_detected)
        self.cap_thread.eye_lost.connect(self.tracker.on_eye_lost)

        # Buttons
        self.controls.btn_stream.clicked.connect(self._toggle_stream)
        self.controls.btn_calibrate.clicked.connect(self.tracker.calibrate)
        self.controls.btn_reset_view.clicked.connect(self._reset_3d_view)
        self.controls.btn_play_movement.clicked.connect(self._toggle_movement)

        # Parameter spin-boxes / combos → tracker
        for widget in (
            self.controls.spin_ws_w, self.controls.spin_ws_h,
            self.controls.spin_eye_dist,
            self.controls.spin_camera_x, self.controls.spin_camera_y,
            self.controls.spin_camera_z,
            self.controls.spin_light_x, self.controls.spin_light_y,
            self.controls.spin_light_z,
        ):
            widget.valueChanged.connect(self._on_params_changed)
        self.controls.combo_vehicle.currentIndexChanged.connect(self._on_params_changed)

    # ── slots ───────────────────────────────────────────────────────

    def _toggle_stream(self, checked):
        if checked:
            if self.cap_thread.isRunning():
                return
            self.controls.btn_stream.setText("⏹  Stop Stream")
            self._push_config()
            self.cap_thread.start()
            self.readout.set_value("status", "ACTIVE ●", "#4caf50")
        else:
            self.controls.btn_stream.setText("▶  Start Stream")
            self.cap_thread.stop()
            self.video_widget.clear_feed()
            self.scene_3d.hide_tracking()
            self.windshield_2d.clear_glare()
            self.tracker.reset_on_stream_stop()
            self.readout.set_value("status", "STOPPED ○", "#666")

    def _push_config(self):
        self.cap_thread.update_config(TrackingConfig(
            self.controls.spin_ws_w.value(),
            self.controls.spin_ws_h.value(),
            self.controls.spin_eye_dist.value(),
            *self.controls.get_camera_pos(),
        ))

    def _on_params_changed(self):
        if self.cap_thread.isRunning():
            self._push_config()
        self.tracker.on_params_changed()

    def _toggle_movement(self, playing):
        if playing:
            self.controls.btn_play_movement.setText("⏹  Stop Light Movement")
            self.tracker.start_movement()
            self._movement_timer.start()
        else:
            self._movement_timer.stop()
            self.tracker.stop_movement()
            self.controls.btn_play_movement.setText("▶  Play Light Movement")
            self.tracker.on_params_changed()

    def _reset_3d_view(self):
        self.scene_3d.gl_view.setCameraPosition(distance=140, elevation=20, azimuth=-45)

    # ── responsive layout ───────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 1050
        self.main_splitter.setOrientation(Qt.Vertical if narrow else Qt.Horizontal)
        sidebar = self.main_splitter.widget(1)
        if narrow:
            sidebar.setMinimumWidth(0)
            sidebar.setMaximumWidth(16777215)
        else:
            sidebar.setMinimumWidth(280)
            sidebar.setMaximumWidth(420)

    # ── clean shutdown ──────────────────────────────────────────────

    def closeEvent(self, event):
        self._movement_timer.stop()
        self.cap_thread.stop()
        if self.cap_thread.isRunning():
            event.ignore()
            return
        event.accept()

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _application_icon():
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return QIcon(os.path.join(base, "assets", "glaretracker-icon.ico"))
