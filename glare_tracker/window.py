"""Main application window — layout and signal wiring only.

All tracking logic lives in :class:`~glare_tracker.tracking.TrackingController`.
"""

import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
)

from glare_tracker import __version__
from glare_tracker.camera import VideoCaptureThread
from glare_tracker.headlight_detector import (
    HeadlightDetectorThread, MonocularHeadlightDetectorThread,
)
from glare_tracker.config import TrackingConfig
from glare_tracker.styles import DARK_STYLESHEET
from glare_tracker.tracking import TrackingController
from glare_tracker.widgets import (
    ApplicationHeader, CameraFeedPanel, ControlsPanel, OperationsSidebar,
    ReadoutPanel, Scene3DWidget, SceneWorkspace, Windshield2DWidget,
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
        self.windshield_2d = Windshield2DWidget()
        self.scene_3d = Scene3DWidget()
        self.readout = ReadoutPanel()
        self.controls = ControlsPanel()
        self.header = ApplicationHeader(__version__)
        self.camera_feeds = CameraFeedPanel()
        self.workspace = SceneWorkspace(self.scene_3d, self.windshield_2d)

        # ── tracking controller ──
        self.tracker = TrackingController(
            self.scene_3d, self.windshield_2d, self.readout, self.controls,
        )

        # ── threads ──
        self.cap_thread = VideoCaptureThread(
            camera_index=self.controls.spin_driver_camera.value())
        self.headlight_thread = None
        self._headlight_camera_available = False

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
        self.sidebar = OperationsSidebar(
            [self.readout, self.camera_feeds], self.controls)
        self.sidebar.setMinimumWidth(300)
        self.sidebar.setMaximumWidth(460)

        # Main: viewport | sidebar
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.workspace)
        self.main_splitter.addWidget(self.sidebar)
        self.main_splitter.setSizes([1050, 350])
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(10, 10, 10, 10)
        central_layout.setSpacing(8)
        central_layout.addWidget(self.header)
        central_layout.addWidget(self.main_splitter)
        self.setCentralWidget(central)

    # ── signal wiring ───────────────────────────────────────────────

    def _connect_signals(self):
        # Camera → display + tracker
        self.cap_thread.frame_ready.connect(self._update_driver_frame)
        self.cap_thread.eye_detected.connect(self._on_eye_detected)
        self.cap_thread.eye_lost.connect(self._on_eye_lost)
        self.cap_thread.camera_status.connect(self._on_driver_camera_status)

        # Manual/auto source and camera setup
        self.controls.combo_light_mode.currentTextChanged.connect(self._light_mode_changed)
        self.controls.combo_detection_setup.currentTextChanged.connect(self._auto_setup_changed)
        self.controls.spin_headlight_camera.valueChanged.connect(self._auto_setup_changed)
        self.controls.spin_headlight_camera_2.valueChanged.connect(self._auto_setup_changed)
        self.controls.spin_driver_camera.valueChanged.connect(self._driver_camera_changed)
        self.controls.spin_single_depth.valueChanged.connect(self._update_single_projection)
        self.controls.spin_camera_hfov.valueChanged.connect(self._update_single_projection)
        self.controls.spin_brightness_threshold.valueChanged.connect(
            self._update_detection_settings)

        # Buttons
        self.controls.btn_stream.clicked.connect(self._toggle_stream)
        self.controls.btn_calibrate.clicked.connect(self.tracker.calibrate)
        self.controls.btn_reset_view.clicked.connect(self._reset_3d_view)
        self.controls.btn_play_movement.clicked.connect(self._toggle_movement)
        self.header.panel_toggle.toggled.connect(self.sidebar.setVisible)

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

    def _on_eye_detected(self, x, y, z):
        self.tracker.on_eye_detected(x, y, z)
        self.header.set_tracking("EYE TRACKING", "active")

    def _on_eye_lost(self):
        self.tracker.on_eye_lost()
        self.header.set_tracking("NO FACE", "warning")

    def _update_driver_frame(self, q_img):
        self.camera_feeds.driver.set_frame(q_img)

    def _update_headlight_frame(self, q_img):
        self.camera_feeds.headlight.set_frame(q_img)

    def _on_driver_camera_status(self, message, available):
        self.camera_feeds.driver.set_status(
            message, "active" if available else "error")
        if not available:
            self.camera_feeds.driver.set_placeholder("Camera not detected")
            self.header.set_tracking("CAMERA OFFLINE", "error")

    def _on_headlight_camera_status(self, message, available):
        self._headlight_camera_available = available
        self.camera_feeds.headlight.set_status(
            message, "active" if available else "error")
        if not available:
            self.camera_feeds.headlight.set_placeholder("Camera not detected")

    def _on_auto_headlight(self, x, y, z):
        if self.controls.is_auto_light():
            self._headlight_camera_available = True
            self.camera_feeds.headlight.set_status("Tracking bright light", "active")
            # Update sliders without triggering a signal loop
            self.controls.spin_light_x.blockSignals(True)
            self.controls.spin_light_y.blockSignals(True)
            self.controls.spin_light_z.blockSignals(True)

            self.controls.spin_light_x.setValue(x)
            self.controls.spin_light_y.setValue(y)
            self.controls.spin_light_z.setValue(z)

            self.controls.spin_light_x.blockSignals(False)
            self.controls.spin_light_y.blockSignals(False)
            self.controls.spin_light_z.blockSignals(False)

            self._on_params_changed()

    def _light_mode_changed(self):
        auto = self.controls.is_auto_light()
        self.header.set_mode(auto)
        self.controls.btn_play_movement.setEnabled(not auto)
        if auto:
            if self._movement_timer.isActive():
                self._movement_timer.stop()
                self.tracker.stop_movement()
                self.controls.btn_play_movement.setChecked(False)
                self.controls.btn_play_movement.setText("▶  Play Light Movement")
            self._start_headlight_detection()
        else:
            self._stop_headlight_detection()
            self.camera_feeds.headlight.set_placeholder("Manual coordinates")
            self.camera_feeds.headlight.set_status("Fixed coordinate input", "info")

    def _auto_setup_changed(self):
        if self.controls.is_auto_light():
            self._start_headlight_detection()

    def _driver_camera_changed(self):
        was_running = self.cap_thread.isRunning()
        if was_running:
            self.cap_thread.stop()
        self.cap_thread.deleteLater()
        self.cap_thread = VideoCaptureThread(
            camera_index=self.controls.spin_driver_camera.value())
        self.cap_thread.frame_ready.connect(self._update_driver_frame)
        self.cap_thread.eye_detected.connect(self._on_eye_detected)
        self.cap_thread.eye_lost.connect(self._on_eye_lost)
        self.cap_thread.camera_status.connect(self._on_driver_camera_status)
        if was_running:
            self._push_config()
            self.camera_feeds.driver.set_status("Opening camera...", "warning")
            self.cap_thread.start()

    def _start_headlight_detection(self):
        self._stop_headlight_detection()
        cam1 = self.controls.spin_headlight_camera.value()
        ws_h = self.controls.spin_ws_h.value()
        if self.controls.is_stereo_detection():
            self.headlight_thread = HeadlightDetectorThread(
                cam1_idx=cam1,
                cam2_idx=self.controls.spin_headlight_camera_2.value(),
                camera_height_cm=ws_h,
                brightness_threshold=self.controls.spin_brightness_threshold.value(),
            )
        else:
            self.headlight_thread = MonocularHeadlightDetectorThread(
                camera_index=cam1,
                depth_cm=self.controls.spin_single_depth.value(),
                windshield_h_cm=ws_h,
                hfov_deg=self.controls.spin_camera_hfov.value(),
                brightness_threshold=self.controls.spin_brightness_threshold.value(),
            )
        self.headlight_thread.frame_ready.connect(self._update_headlight_frame)
        self.headlight_thread.headlight_detected.connect(self._on_auto_headlight)
        self.headlight_thread.headlight_lost.connect(self._on_headlight_lost)
        self.headlight_thread.camera_status.connect(self._on_headlight_camera_status)
        self.camera_feeds.headlight.set_status("Opening camera...", "warning")
        self.headlight_thread.start()

    def _stop_headlight_detection(self):
        if self.headlight_thread is not None:
            self.headlight_thread.stop()
            self.headlight_thread.deleteLater()
            self.headlight_thread = None
        self._headlight_camera_available = False

    def _on_headlight_lost(self):
        if (self.controls.is_auto_light() and self.headlight_thread is not None
                and self._headlight_camera_available):
            self.camera_feeds.headlight.set_status(
                "Camera connected - no bright light detected", "warning")

    def _update_single_projection(self):
        if isinstance(self.headlight_thread, MonocularHeadlightDetectorThread):
            self.headlight_thread.update_projection(
                self.controls.spin_single_depth.value(),
                self.controls.spin_ws_h.value(),
                self.controls.spin_camera_hfov.value(),
                self.controls.spin_brightness_threshold.value(),
            )

    def _update_detection_settings(self):
        self._update_single_projection()
        if isinstance(self.headlight_thread, HeadlightDetectorThread):
            self.headlight_thread.update_detection_threshold(
                self.controls.spin_brightness_threshold.value())

    def _toggle_stream(self, checked):
        if checked:
            if self.cap_thread.isRunning():
                return
            self.controls.btn_stream.setText("⏹  Stop Stream")
            self._push_config()
            self.cap_thread.start()
            self.readout.set_value("status", "ACTIVE ●", "#4caf50")
            self.header.set_tracking("STARTING", "warning")
            self.camera_feeds.driver.set_status("Opening camera...", "warning")
        else:
            self.controls.btn_stream.setText("▶  Start Stream")
            self.cap_thread.stop()
            self.camera_feeds.driver.set_placeholder("Driver camera stopped")
            self.scene_3d.hide_tracking()
            self.windshield_2d.clear_glare()
            self.tracker.reset_on_stream_stop()
            self.readout.set_value("status", "STOPPED ○", "#666")
            self.camera_feeds.driver.set_status("Stream stopped", "idle")
            self.header.set_tracking("SYSTEM IDLE", "idle")

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
        self._update_single_projection()

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
        if narrow:
            self.sidebar.setMinimumWidth(0)
            self.sidebar.setMaximumWidth(16777215)
        else:
            self.sidebar.setMinimumWidth(300)
            self.sidebar.setMaximumWidth(460)

    # ── clean shutdown ──────────────────────────────────────────────

    def closeEvent(self, event):
        self._movement_timer.stop()
        self.cap_thread.stop()
        self._stop_headlight_detection()
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
