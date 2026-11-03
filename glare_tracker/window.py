"""Main application window — layout and signal wiring only.

All tracking logic lives in :class:`~glare_tracker.tracking.TrackingController`.
"""

from dataclasses import asdict
import os
from pathlib import Path
import sys
import time

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QImage
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QMessageBox,
    QSizePolicy,
)

from glare_tracker import __version__
from glare_tracker.calibration import (
    load_driver_depth_calibration,
    load_monocular_range_calibration,
)
from glare_tracker.camera import VideoCaptureThread
from glare_tracker.capture import CameraDiscoveryThread
from glare_tracker.headlight_detector import (
    HeadlightDetectorThread, MonocularHeadlightDetectorThread,
)
from glare_tracker.config import TrackingConfig
from glare_tracker.diagnostics import DiagnosticRecorder
from glare_tracker.lcd_blocker import LCDBlockerWindow
from glare_tracker.operating_modes import (
    OperatingMode, SessionState, calculations_enabled, cameras_enabled,
)
from glare_tracker.styles import DARK_STYLESHEET
from glare_tracker.widgets.stereo_calibration import StereoCalibrationDialog
from glare_tracker.tracking import TrackingController
from glare_tracker.widgets import (
    ApplicationHeader, CameraFeedPanel, ConfigurationSidebar, ControlsPanel,
    ReadoutPanel, Scene3DWidget, SceneWorkspace, Windshield2DWidget,
    GuidedCalibrationWizard, IconFactory,
)


class MainWindow(QMainWindow):
    """Assembles all panels and wires signals to the tracking controller."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Windshield Glare Tracking System")
        self.setWindowIcon(self._application_icon())
        self.setMinimumSize(960, 640)
        self._set_initial_geometry()
        self.setStyleSheet(DARK_STYLESHEET)

        # ── widgets ──
        self.windshield_2d = Windshield2DWidget()
        self.scene_3d = Scene3DWidget()
        self.readout = ReadoutPanel()
        self.controls = ControlsPanel()
        self.header = ApplicationHeader(__version__)
        self.camera_feeds = CameraFeedPanel()
        self.workspace = SceneWorkspace(self.scene_3d, self.windshield_2d)
        self._session_state = SessionState.STOP
        self._driver_source_was_manual = self.controls.mode_policy().manual_driver
        self._road_source_was_manual = self.controls.mode_policy().manual_headlight
        self._road_position_ready = False
        self.diagnostics = DiagnosticRecorder()
        self.lcd_blocker = LCDBlockerWindow()
        self._latest_pipeline_timing = {}
        self._maximum_sample_age_ms = 250.0

        # Saved demonstration calibration profiles
        try:
            self._driver_depth_calibration = load_driver_depth_calibration()
        except Exception:
            self._driver_depth_calibration = None
        try:
            self._road_range_calibration = load_monocular_range_calibration()
        except Exception:
            self._road_range_calibration = None
        self._refresh_calibration_controls()
        self.controls.check_driver_depth_calibration.setChecked(
            self.controls.check_driver_depth_calibration.isEnabled())
        self.controls.check_road_range_calibration.setChecked(
            self.controls.check_road_range_calibration.isEnabled())

        # ── tracking controller ──
        self.tracker = TrackingController(
            self.scene_3d, self.windshield_2d, self.readout, self.controls,
            diagnostics=self.diagnostics,
            lcd_blocker=self.lcd_blocker,
        )

        # ── threads ──
        self.cap_thread = VideoCaptureThread(
            camera_index=self.controls.spin_driver_camera.value())
        self.headlight_thread = None
        self._headlight_camera_available = False
        self._camera_discovery_thread = None

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
        self._operating_mode_changed()
        self.tracker.on_params_changed(calculate=False)
        if QApplication.platformName().lower() != "offscreen":
            QTimer.singleShot(150, self._refresh_available_cameras)

    # ── layout ──────────────────────────────────────────────────────

    def _build_layout(self):
        self.sidebar = ConfigurationSidebar(self.controls)
        self.sidebar.setMinimumWidth(380)
        self.sidebar.setMaximumWidth(500)

        self.visual_column = QWidget()
        visual_layout = QVBoxLayout(self.visual_column)
        visual_layout.setContentsMargins(0, 0, 0, 0)
        visual_layout.setSpacing(0)
        self.visual_splitter = QSplitter(Qt.Vertical)
        self.visual_splitter.setObjectName("visualSplitter")
        self.visual_splitter.setChildrenCollapsible(False)
        self.visual_splitter.setHandleWidth(5)
        self.visual_splitter.addWidget(self.workspace)

        # Independent lower panels: camera feeds on the left and telemetry on
        # the right. Neither panel owns the other, and their divider is movable.
        self.bottom_splitter = QSplitter(Qt.Horizontal)
        self.bottom_splitter.setObjectName("bottomSplitter")
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.setHandleWidth(5)
        self.bottom_splitter.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.readout.setProperty("overlay", False)
        self.readout.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.readout.setMinimumWidth(320)
        self.readout.setMaximumWidth(430)
        self.bottom_splitter.addWidget(self.camera_feeds)
        self.bottom_splitter.addWidget(self.readout)
        self.bottom_splitter.setStretchFactor(0, 1)
        self.bottom_splitter.setStretchFactor(1, 0)
        self.bottom_splitter.setSizes([900, 380])

        self.visual_splitter.addWidget(self.bottom_splitter)
        self.visual_splitter.setStretchFactor(0, 1)
        self.visual_splitter.setStretchFactor(1, 0)
        self.visual_splitter.setSizes([650, 300])
        visual_layout.addWidget(self.visual_splitter)

        # Main: visual operations workspace | dedicated configuration panel
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.visual_column)
        self.main_splitter.addWidget(self.sidebar)
        self.main_splitter.setSizes([1080, 460])
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
        self.cap_thread.eyes_detected.connect(self._on_eyes_detected)
        self.cap_thread.eye_lost.connect(self._on_eye_lost)
        self.cap_thread.camera_status.connect(self._on_driver_camera_status)
        self.cap_thread.pipeline_timing.connect(self._on_pipeline_timing)

        # Operating mode and camera setup
        self.controls.combo_operating_mode.currentTextChanged.connect(
            self._operating_mode_changed)
        self.controls.combo_detection_setup.currentTextChanged.connect(
            self._camera_setup_changed)
        self.controls.spin_headlight_camera.valueChanged.connect(
            self._camera_setup_changed)
        self.controls.spin_headlight_camera_2.valueChanged.connect(
            self._camera_setup_changed)
        self.controls.spin_driver_camera.valueChanged.connect(self._driver_camera_changed)
        self.controls.btn_refresh_cameras.clicked.connect(
            self._refresh_available_cameras)
        self.controls.btn_stereo_calibration.clicked.connect(self._open_stereo_calibration)
        self.controls.spin_single_depth.valueChanged.connect(self._update_single_projection)
        self.controls.spin_camera_hfov.valueChanged.connect(self._update_single_projection)
        self.controls.spin_brightness_threshold.valueChanged.connect(
            self._update_detection_settings)
        for widget in (
            self.controls.spin_exposure,
            self.controls.spin_camera_brightness,
            self.controls.spin_camera_contrast,
            self.controls.spin_camera_gain,
            self.controls.spin_min_light_area,
            self.controls.spin_max_light_area,
            self.controls.spin_morphology_iterations,
            self.controls.spin_max_light_sources,
            self.controls.spin_light_match_distance,
            self.controls.spin_background_difference,
            self.controls.spin_local_contrast_threshold,
            self.controls.spin_min_source_confidence,
        ):
            widget.valueChanged.connect(self._update_detection_settings)
        for widget in (
            self.controls.check_apply_camera_controls,
            self.controls.check_auto_exposure,
            self.controls.check_adaptive_threshold,
            self.controls.check_background_rejection,
            self.controls.check_local_contrast,
        ):
            widget.toggled.connect(self._update_detection_settings)
        self.controls.combo_blur_size.currentTextChanged.connect(
            self._update_detection_settings)
        self.camera_feeds.headlight.preview_mode_changed.connect(
            lambda mode: self._update_road_preview_mode(1, mode))
        self.camera_feeds.headlight_secondary.preview_mode_changed.connect(
            lambda mode: self._update_road_preview_mode(2, mode))
        self.controls.btn_capture_background.clicked.connect(
            self._capture_light_background)
        self.controls.btn_clear_background.clicked.connect(
            self._clear_light_background)
        self.controls.btn_daylight_phone_preset.clicked.connect(
            self._activate_phone_light_diagnostics)

        # Buttons
        self.header.btn_run.clicked.connect(
            lambda: self._set_session_state(SessionState.RUN))
        self.header.btn_standby.clicked.connect(
            lambda: self._set_session_state(SessionState.STANDBY))
        self.header.btn_stop.clicked.connect(
            lambda: self._set_session_state(SessionState.STOP))
        self.header.btn_calibrate.clicked.connect(self.tracker.calibrate)
        self.header.btn_reset_view.clicked.connect(self._reset_3d_view)
        self.controls.btn_play_movement.clicked.connect(self._toggle_movement)
        self.controls.btn_guided_calibration.clicked.connect(
            self._open_guided_calibration)
        self.controls.check_driver_depth_calibration.stateChanged.connect(
            self._calibration_options_changed)
        self.controls.check_road_range_calibration.stateChanged.connect(
            self._calibration_options_changed)
        self.controls.check_record_diagnostics.toggled.connect(
            self._diagnostics_recording_changed)
        self.controls.btn_mark_ground_truth.clicked.connect(
            self._record_ground_truth_marker)
        self.controls.check_lcd_output.toggled.connect(
            self._lcd_output_changed)
        self.controls.spin_lcd_radius.valueChanged.connect(
            self._refresh_lcd_configuration)
        self.header.panel_toggle.toggled.connect(self.sidebar.setVisible)
        self.scene_3d.scene_theme_changed.connect(self.windshield_2d.set_light_theme)

        # Parameter spin-boxes / combos → tracker
        for widget in (
            self.controls.spin_ws_w, self.controls.spin_ws_h,
            self.controls.spin_eye_dist,
            self.controls.spin_camera_x, self.controls.spin_camera_y,
            self.controls.spin_camera_z,
            self.controls.spin_light_x, self.controls.spin_light_y,
            self.controls.spin_light_z,
            self.controls.spin_driver_x, self.controls.spin_driver_y,
            self.controls.spin_driver_z,
        ):
            widget.valueChanged.connect(self._on_params_changed)
        self.controls.combo_vehicle.currentIndexChanged.connect(self._on_params_changed)

    # ── slots ───────────────────────────────────────────────────────

    def _on_eye_detected(self, x, y, z):
        """Compatibility slot for midpoint-only driver sources."""
        if not calculations_enabled(self._session_state):
            return
        callback_started_ns = time.monotonic_ns()
        if not self._sample_is_fresh("driver", callback_started_ns):
            self.tracker.on_eye_lost()
            self.header.set_tracking("STALE EYE SAMPLE", "warning")
            return
        self.tracker.on_eye_detected(x, y, z)
        self._record_geometry_timing(
            "driver", callback_started_ns, time.monotonic_ns()
        )
        self.header.set_tracking("EYE TRACKING", "active")

    def _on_eyes_detected(self, lx, ly, lz, rx, ry, rz):
        """Accept both eyes without collapsing their relative geometry."""
        if not calculations_enabled(self._session_state):
            return
        callback_started_ns = time.monotonic_ns()
        if not self._sample_is_fresh("driver", callback_started_ns):
            self.tracker.on_eye_lost()
            self.header.set_tracking("STALE EYE SAMPLE", "warning")
            return
        self.tracker.on_eyes_detected(lx, ly, lz, rx, ry, rz)
        self._record_geometry_timing(
            "driver", callback_started_ns, time.monotonic_ns()
        )
        self.header.set_tracking("BOTH EYES TRACKING", "active")

    def _on_eye_lost(self):
        self.diagnostics.record_event("eye_lost")
        if not calculations_enabled(self._session_state):
            return
        self.tracker.on_eye_lost()
        self.header.set_tracking("NO FACE", "warning")

    def _update_driver_frame(self, q_img):
        self.camera_feeds.driver.set_frame(q_img)
        self._record_preview_timing("driver")
        self._record_qimage("driver", q_img)

    def _update_headlight_frame(self, q_img):
        self.camera_feeds.headlight.set_frame(q_img)
        self._record_preview_timing("road_primary")
        self._record_qimage("road_primary", q_img)

    def _update_stereo_frames(self, primary, secondary):
        self.camera_feeds.set_stereo_frames(primary, secondary)
        self._record_preview_timing("road_stereo")
        self._record_qimage("road_primary", primary)
        self._record_qimage("road_secondary", secondary)

    def _record_qimage(self, stream, image):
        """Copy a Qt preview frame into the asynchronous diagnostics queue."""

        if not self.diagnostics.is_active:
            return
        converted = image.convertToFormat(QImage.Format_RGB888)
        pointer = converted.bits()
        pointer.setsize(converted.byteCount())
        padded = np.frombuffer(pointer, dtype=np.uint8).reshape(
            converted.height(), converted.bytesPerLine()
        )
        rgb = padded[:, : converted.width() * 3].reshape(
            converted.height(), converted.width(), 3
        )
        self.diagnostics.record_frame(stream, rgb)

    def _on_pipeline_timing(self, payload):
        """Capture worker timestamps before the corresponding tracking callback."""

        details = dict(payload)
        details["gui_received_ns"] = time.monotonic_ns()
        stream = str(details.get("stream", "unknown"))
        self._latest_pipeline_timing[stream] = details
        self.diagnostics.record_event("pipeline_capture", details=details)

    def _sample_is_fresh(self, stream, now_ns):
        timing = self._latest_pipeline_timing.get(stream)
        if timing is None:
            return True
        captured_ns = int(timing.get("capture_complete_ns", now_ns))
        age_ms = (now_ns - captured_ns) / 1_000_000.0
        if age_ms <= self._maximum_sample_age_ms:
            return True
        self.diagnostics.record_event(
            "stale_sample_rejected",
            details={
                "stream": stream,
                "frame_index": timing.get("frame_index"),
                "sample_age_ms": age_ms,
                "maximum_sample_age_ms": self._maximum_sample_age_ms,
            },
        )
        return False

    def _record_geometry_timing(self, stream, callback_started_ns, completed_ns):
        timing = self._latest_pipeline_timing.get(stream, {})
        details = {
            "stream": stream,
            "frame_index": timing.get("frame_index"),
            "capture_complete_ns": timing.get("capture_complete_ns"),
            "detection_complete_ns": timing.get("detection_complete_ns"),
            "callback_started_ns": callback_started_ns,
            "geometry_complete_ns": completed_ns,
        }
        self.diagnostics.record_event("pipeline_geometry", details=details)

    def _record_preview_timing(self, stream):
        timing = self._latest_pipeline_timing.get(stream, {})
        self.diagnostics.record_event(
            "pipeline_preview_queued",
            details={
                "stream": stream,
                "frame_index": timing.get("frame_index"),
                "capture_complete_ns": timing.get("capture_complete_ns"),
                "preview_queued_ns": time.monotonic_ns(),
            },
        )

    def _diagnostics_recording_changed(self, enabled):
        """Start or finalize a timestamped research recording session."""

        if enabled:
            output_root = Path(
                os.environ.get(
                    "GLARETRACKER_DIAGNOSTICS_DIR",
                    str(Path.cwd() / "diagnostics"),
                )
            )
            metadata = {
                "application_version": __version__,
                "operating_mode": self.controls.operating_mode().value,
                "detection_setup": (
                    self.controls.combo_detection_setup.currentText()
                ),
                "driver_camera_index": self.controls.spin_driver_camera.value(),
                "road_camera_index": self.controls.spin_headlight_camera.value(),
                "secondary_road_camera_index": (
                    self.controls.spin_headlight_camera_2.value()
                ),
                "windshield_width_cm": self.controls.spin_ws_w.value(),
                "windshield_height_cm": self.controls.spin_ws_h.value(),
                "light_detection_settings": asdict(
                    self.controls.get_light_detection_settings()
                ),
            }
            try:
                session_dir = self.diagnostics.start(
                    output_root, metadata=metadata
                )
            except Exception as error:
                self.controls.check_record_diagnostics.blockSignals(True)
                self.controls.check_record_diagnostics.setChecked(False)
                self.controls.check_record_diagnostics.blockSignals(False)
                self.controls.diagnostics_status.setText(
                    f"Recording could not start: {error}"
                )
                return
            self.diagnostics.record_event(
                "session_state", details={"state": self._session_state.value}
            )
            self.controls.diagnostics_status.setText(
                f"Recording to {session_dir}"
            )
            return

        session_dir = self.diagnostics.stop()
        if session_dir is None:
            self.controls.diagnostics_status.setText("Recording is off")
        elif self.diagnostics.errors:
            self.controls.diagnostics_status.setText(
                f"Saved to {session_dir} with "
                f"{len(self.diagnostics.errors)} recording error(s)"
            )
        else:
            self.controls.diagnostics_status.setText(f"Saved to {session_dir}")

    def _record_ground_truth_marker(self):
        """Timestamp an operator-measured point inside the active CSV log."""

        if not self.diagnostics.is_active:
            self.controls.ground_truth_status.setText(
                "Start research recording before marking a measured position."
            )
            return
        target = self.controls.combo_ground_truth_target.currentText()
        label = self.controls.edit_ground_truth_label.text().strip()
        position = (
            self.controls.spin_ground_truth_x.value(),
            self.controls.spin_ground_truth_y.value(),
            self.controls.spin_ground_truth_z.value(),
        )
        self.diagnostics.record_ground_truth(target, position, label=label)
        self.controls.ground_truth_status.setText(
            f"Marked {label or target}: "
            f"X {position[0]:.1f}, Y {position[1]:.1f}, Z {position[2]:.1f} cm"
        )

    def _lcd_output_changed(self, enabled):
        """Explicitly enable experimental output only on a secondary display."""

        if not enabled:
            self.lcd_blocker.disable_output()
            self.controls.lcd_status.setText(
                "Disabled; secondary output cleared to white."
            )
            self.diagnostics.record_event("lcd_output_disabled")
            return
        screens = QApplication.screens()
        if len(screens) < 2:
            self.controls.check_lcd_output.blockSignals(True)
            self.controls.check_lcd_output.setChecked(False)
            self.controls.check_lcd_output.blockSignals(False)
            self.controls.lcd_status.setText(
                "No secondary display detected; output remains safely disabled."
            )
            return
        self._refresh_lcd_configuration()
        self.lcd_blocker.enable_on_screen(screens[1])
        self.controls.lcd_status.setText(
            f"Enabled on secondary display: {screens[1].name()}"
        )
        self.diagnostics.record_event(
            "lcd_output_enabled",
            details={
                "screen": screens[1].name(),
                "resolution": [
                    screens[1].geometry().width(),
                    screens[1].geometry().height(),
                ],
                "radius_px": self.controls.spin_lcd_radius.value(),
            },
        )
        self.tracker.on_params_changed(
            calculate=self._coordinates_ready_for_calculation()
        )

    def _refresh_lcd_configuration(self):
        screens = QApplication.screens()
        screen = screens[1] if len(screens) > 1 else screens[0]
        geometry = screen.geometry()
        self.lcd_blocker.configure_panel(
            self.controls.spin_ws_w.value(),
            self.controls.spin_ws_h.value(),
            (geometry.width(), geometry.height()),
            self.controls.spin_lcd_radius.value(),
        )

    def _on_driver_camera_status(self, message, available):
        self.diagnostics.record_event(
            "driver_camera_status",
            message=message,
            details={"available": bool(available)},
        )
        self.camera_feeds.driver.set_status(
            message, "active" if available else "error")
        if not available:
            self.camera_feeds.driver.set_placeholder("Camera not detected")
            self.header.set_tracking("CAMERA OFFLINE", "error")

    def _on_headlight_camera_status(self, message, available):
        self.diagnostics.record_event(
            "road_camera_status",
            message=message,
            details={"available": bool(available)},
        )
        self._headlight_camera_available = available
        self.camera_feeds.headlight.set_status(
            message, "active" if available else "error")
        if self.controls.is_stereo_detection():
            self.camera_feeds.headlight_secondary.set_status(
                message, "active" if available else "error")
        if not available:
            self.camera_feeds.headlight.set_placeholder("Camera not detected")
            if self.controls.is_stereo_detection():
                self.camera_feeds.headlight_secondary.set_placeholder(
                    "Camera not detected")

    def _on_auto_lights(self, sources):
        """Consume real independent lights without vehicle-offset modeling."""

        if (not calculations_enabled(self._session_state)
                or not self.controls.mode_policy().use_road_camera
                or not sources):
            return
        stream = (
            "road_stereo"
            if self.controls.is_stereo_detection()
            else "road_primary"
        )
        callback_started_ns = time.monotonic_ns()
        if not self._sample_is_fresh(stream, callback_started_ns):
            self._road_position_ready = False
            self.tracker.on_lights_lost()
            self.camera_feeds.headlight.set_status(
                "Stale road-camera sample rejected", "warning"
            )
            return
        observed_after = time.time() - self._maximum_sample_age_ms / 1000.0
        fresh_sources = [
            source
            for source in sources
            if source.timestamp >= observed_after
        ]
        if not fresh_sources:
            self._road_position_ready = False
            self.tracker.on_lights_lost()
            self.diagnostics.record_event(
                "stale_light_sources_rejected",
                details={
                    "source_count": len(sources),
                    "maximum_sample_age_ms": self._maximum_sample_age_ms,
                },
            )
            self.camera_feeds.headlight.set_status(
                "Stale light observation rejected", "warning"
            )
            return
        if len(fresh_sources) != len(sources):
            self.diagnostics.record_event(
                "stale_light_sources_filtered",
                details={
                    "received": len(sources),
                    "accepted": len(fresh_sources),
                },
            )
        sources = fresh_sources
        self._road_position_ready = True
        self._headlight_camera_available = True
        count = len(sources)
        self.camera_feeds.headlight.set_status(
            f"Tracking {count} independent light source"
            f"{'s' if count != 1 else ''}",
            "active",
        )

        # Keep the first source visible in the legacy coordinate controls for
        # operator reference. Geometry receives the complete source list.
        x, y, z = sources[0].position
        for control, value in (
            (self.controls.spin_light_x, x),
            (self.controls.spin_light_y, y),
            (self.controls.spin_light_z, z),
        ):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)
        self.tracker.on_lights_detected(sources, calculate=True)
        self._record_geometry_timing(
            stream, callback_started_ns, time.monotonic_ns()
        )

    def _on_auto_headlight(self, x, y, z):
        """Compatibility slot for older single-point detector workers."""
        if (calculations_enabled(self._session_state)
                and self.controls.mode_policy().use_road_camera):
            self._road_position_ready = True
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

    def _operating_mode_changed(self):
        policy = self.controls.mode_policy()
        if policy.manual_driver != self._driver_source_was_manual:
            # A coordinate produced by one source must never leak into a mode
            # that expects the other source.
            self.tracker.reset_on_stream_stop()
        self._driver_source_was_manual = policy.manual_driver
        if policy.manual_headlight != self._road_source_was_manual:
            self._road_position_ready = False
            self.tracker.on_lights_lost()
        self._road_source_was_manual = policy.manual_headlight
        self.header.set_mode(self.controls.operating_mode().value)
        stereo = policy.use_road_camera and self.controls.is_stereo_detection()
        self.camera_feeds.configure_sources(
            policy.use_driver_camera, policy.use_road_camera, stereo)
        self.controls.btn_play_movement.setEnabled(
            policy.manual_headlight
            and calculations_enabled(self._session_state))
        self.header.btn_calibrate.setEnabled(
            policy.use_driver_camera
            and calculations_enabled(self._session_state))

        if not policy.manual_headlight and self._movement_timer.isActive():
            self._stop_movement_simulation()

        if cameras_enabled(self._session_state):
            self._ensure_required_cameras()
        else:
            self._stop_headlight_detection()
            if self.cap_thread.isRunning():
                self.cap_thread.stop()

        self._refresh_calibration_controls()
        self.tracker.on_params_changed(
            calculate=self._coordinates_ready_for_calculation())

    def _coordinates_ready_for_calculation(self):
        """Return whether every camera-sourced coordinate has live data."""
        if not calculations_enabled(self._session_state):
            return False
        policy = self.controls.mode_policy()
        return not policy.use_road_camera or self._road_position_ready

    def _set_session_state(self, state: SessionState | str):
        """Apply the Run/Standby/Stop policy to cameras and calculations."""
        if not isinstance(state, SessionState):
            state = SessionState(state)

        self._session_state = state
        self.diagnostics.record_event(
            "session_state", details={"state": state.value}
        )
        self.header.set_session_state(state.value)
        policy = self.controls.mode_policy()

        self.controls.btn_play_movement.setEnabled(
            state is SessionState.RUN and policy.manual_headlight)
        self.header.btn_calibrate.setEnabled(
            state is SessionState.RUN and policy.use_driver_camera)

        if state is SessionState.STOP:
            self._road_position_ready = False
            self._stop_movement_simulation()
            self.cap_thread.stop()
            self._stop_headlight_detection()
            self.camera_feeds.driver.set_placeholder("Driver camera stopped")
            self.camera_feeds.headlight.set_placeholder("Road camera stopped")
            self.camera_feeds.headlight_secondary.set_placeholder(
                "Stereo camera stopped")
            self.camera_feeds.driver.set_status("Session stopped", "idle")
            self.camera_feeds.headlight.set_status("Session stopped", "idle")
            self.camera_feeds.headlight_secondary.set_status(
                "Session stopped", "idle")
            self.scene_3d.hide_tracking()
            self.windshield_2d.clear_glare()
            self.tracker.reset_on_stream_stop()
            self.readout.set_intersections([])
            self.readout.set_value("eye_pos", "— stopped", "#666")
            self.readout.set_value("status", "STOPPED ○", "#666")
            self.header.set_tracking("SYSTEM IDLE", "idle")
            return

        self._ensure_required_cameras()
        if state is SessionState.STANDBY:
            self._stop_movement_simulation()
            self.readout.set_value("status", "STANDBY ○", "#ffb74d")
            self.header.set_tracking("STANDBY", "warning")
            return

        # Entering Run immediately evaluates fixed/manual coordinates. Camera
        # modes update when their next accepted tracking result arrives.
        self.tracker.on_params_changed(
            calculate=self._coordinates_ready_for_calculation())
        if policy.use_driver_camera or policy.use_road_camera:
            self.readout.set_value("status", "WAITING FOR TRACKING", "#ffb74d")
            self.header.set_tracking("STARTING", "warning")
        else:
            self.header.set_tracking("MANUAL GEOMETRY", "active")

    def _ensure_required_cameras(self):
        """Start only the camera workers required by the active mode."""
        policy = self.controls.mode_policy()

        if policy.use_driver_camera:
            if not self.cap_thread.isRunning():
                self._push_config()
                self.camera_feeds.driver.set_status(
                    "Opening camera...", "warning")
                self.cap_thread.start()
        else:
            self.cap_thread.stop()
            self.camera_feeds.driver.set_placeholder(
                "Driver position supplied manually")
            self.camera_feeds.driver.set_status("Manual driver position", "info")

        if policy.use_road_camera:
            if self.headlight_thread is None or not self.headlight_thread.isRunning():
                self._start_headlight_detection()
        else:
            self._stop_headlight_detection()
            self.camera_feeds.headlight.set_placeholder(
                "Headlight position supplied manually")
            self.camera_feeds.headlight_secondary.set_placeholder(
                "Headlight position supplied manually")
            self.camera_feeds.headlight.set_status(
                "Manual headlight position", "info")
            self.camera_feeds.headlight_secondary.set_status(
                "Manual headlight position", "info")

    def _stop_movement_simulation(self):
        """Stop movement and return its button to a consistent idle state."""
        self._movement_timer.stop()
        self.tracker.stop_movement()
        self.controls.btn_play_movement.blockSignals(True)
        self.controls.btn_play_movement.setChecked(False)
        self.controls.btn_play_movement.blockSignals(False)
        self.controls.btn_play_movement.setText("Play Light Movement")
        self.controls.btn_play_movement.setIcon(IconFactory.icon("play"))

    def _camera_setup_changed(self):
        policy = self.controls.mode_policy()
        self._road_position_ready = False
        self.camera_feeds.configure_sources(
            policy.use_driver_camera,
            policy.use_road_camera,
            policy.use_road_camera and self.controls.is_stereo_detection(),
        )
        if cameras_enabled(self._session_state) and policy.use_road_camera:
            self._start_headlight_detection()
        elif not policy.use_road_camera:
            self._stop_headlight_detection()
        self._refresh_calibration_controls()

    def _open_stereo_calibration(self):
        if (self._session_state is not SessionState.STOP
                or self.cap_thread.isRunning()
                or (self.headlight_thread is not None and self.headlight_thread.isRunning())
                or (self._camera_discovery_thread is not None
                    and self._camera_discovery_thread.isRunning())):
            QMessageBox.information(
                self, "Stop cameras first",
                "Select Stop and wait for camera scanning to finish before calibrating.")
            return
        primary = self.controls.spin_headlight_camera.value()
        secondary = self.controls.spin_headlight_camera_2.value()
        if primary == secondary:
            QMessageBox.warning(self, "Select two cameras", "Left and right must use different cameras.")
            return
        dialog = StereoCalibrationDialog(primary, secondary, self)
        dialog.exec_()
        if dialog.saved_path:
            self.controls.stereo_status.setText(
                f"Saved {dialog.saved_path.name}. Run to load; verify measured distances next.")
        dialog.deleteLater()

    def _refresh_available_cameras(self):
        """Populate role dropdowns by probing cameras while the session is stopped."""

        if self._session_state is not SessionState.STOP:
            QMessageBox.information(
                self,
                "Stop cameras before scanning",
                "Select Stop before refreshing the available-camera list.",
            )
            return
        if (self._camera_discovery_thread is not None
                and self._camera_discovery_thread.isRunning()):
            return

        self.controls.btn_refresh_cameras.setEnabled(False)
        self.controls.set_camera_scan_status("Scanning available cameras...")
        self.header.btn_run.setEnabled(False)
        self.header.btn_standby.setEnabled(False)
        self._camera_discovery_thread = CameraDiscoveryThread(
            max_index=10, parent=self)
        self._camera_discovery_thread.cameras_discovered.connect(
            self._on_cameras_discovered)
        self._camera_discovery_thread.finished.connect(
            self._camera_discovery_finished)
        self._camera_discovery_thread.start()

    def _on_cameras_discovered(self, devices):
        self.controls.set_available_cameras(devices)
        if devices:
            noun = "camera" if len(devices) == 1 else "cameras"
            self.controls.set_camera_scan_status(
                f"Found {len(devices)} available {noun}. Choose one for each role."
            )
        else:
            self.controls.set_camera_scan_status(
                "No cameras were available. Close other camera applications "
                "and select Refresh Available Cameras."
            )

    def _camera_discovery_finished(self):
        self.controls.btn_refresh_cameras.setEnabled(True)
        self.header.btn_run.setEnabled(True)
        self.header.btn_standby.setEnabled(True)
        if self._camera_discovery_thread is not None:
            self._camera_discovery_thread.deleteLater()
            self._camera_discovery_thread = None

    def _driver_camera_changed(self):
        was_running = self.cap_thread.isRunning()
        if was_running:
            self.cap_thread.stop()
        self.cap_thread.deleteLater()
        self.cap_thread = VideoCaptureThread(
            camera_index=self.controls.spin_driver_camera.value())
        self.cap_thread.frame_ready.connect(self._update_driver_frame)
        self.cap_thread.eyes_detected.connect(self._on_eyes_detected)
        self.cap_thread.eye_lost.connect(self._on_eye_lost)
        self.cap_thread.camera_status.connect(self._on_driver_camera_status)
        self.cap_thread.pipeline_timing.connect(self._on_pipeline_timing)
        if was_running:
            self._push_config()
            self.camera_feeds.driver.set_status("Opening camera...", "warning")
            self.cap_thread.start()
        self._refresh_calibration_controls()

    def _start_headlight_detection(self):
        if not self._stop_headlight_detection():
            return
        self._road_position_ready = False
        cam1 = self.controls.spin_headlight_camera.value()
        driver_cam = self.controls.spin_driver_camera.value()
        driver_in_use = self.controls.mode_policy().use_driver_camera
        if driver_in_use and cam1 == driver_cam:
            self.camera_feeds.headlight.set_status(
                "Road and driver cameras must use different indices", "error")
            self.camera_feeds.headlight.set_placeholder(
                f"Camera {cam1} is already used for eye tracking")
            return
        ws_h = self.controls.spin_ws_h.value()
        detection_settings = self.controls.get_light_detection_settings()
        if self.controls.is_stereo_detection():
            cam2 = self.controls.spin_headlight_camera_2.value()
            if cam2 == cam1:
                self.camera_feeds.headlight.set_status(
                    "Primary and secondary road cameras must differ", "error")
                self.camera_feeds.headlight_secondary.set_status(
                    "Choose a different camera index", "error")
                return
            if driver_in_use and cam2 == driver_cam:
                self.camera_feeds.headlight.set_status(
                    "Stereo cameras must differ from the driver camera", "error")
                self.camera_feeds.headlight.set_placeholder(
                    f"Camera {cam2} is already used for eye tracking")
                return
            self.headlight_thread = HeadlightDetectorThread(
                cam1_idx=cam1,
                cam2_idx=cam2,
                camera_height_cm=ws_h,
                brightness_threshold=self.controls.spin_brightness_threshold.value(),
                detection_settings=detection_settings,
            )
        else:
            self.headlight_thread = MonocularHeadlightDetectorThread(
                camera_index=cam1,
                depth_cm=self.controls.spin_single_depth.value(),
                windshield_h_cm=ws_h,
                hfov_deg=self.controls.spin_camera_hfov.value(),
                brightness_threshold=self.controls.spin_brightness_threshold.value(),
                detection_settings=detection_settings,
                use_range_calibration=(
                    self.controls.check_road_range_calibration.isChecked()),
            )
        if isinstance(self.headlight_thread, HeadlightDetectorThread):
            self.headlight_thread.stereo_diagnostics.connect(self.controls.stereo_status.setText)
            self.headlight_thread.stereo_frames_ready.connect(
                self._update_stereo_frames)
        else:
            self.headlight_thread.frame_ready.connect(self._update_headlight_frame)
        self.headlight_thread.lights_detected.connect(self._on_auto_lights)
        self.headlight_thread.headlight_lost.connect(self._on_headlight_lost)
        self.headlight_thread.camera_status.connect(self._on_headlight_camera_status)
        self.headlight_thread.camera_controls_report.connect(
            self._on_camera_controls_report)
        self.headlight_thread.background_status.connect(
            self.controls.set_background_status)
        self.headlight_thread.pipeline_timing.connect(self._on_pipeline_timing)
        self.camera_feeds.headlight.set_status("Opening camera...", "warning")
        self.controls.set_background_status(
            "No background captured for this camera session. In Standby, "
            "remove the test light and capture the static scene.")
        if self.controls.is_stereo_detection():
            self.camera_feeds.headlight_secondary.set_status(
                "Opening camera...", "warning")
        self._update_road_preview_mode(
            1, self.camera_feeds.headlight.preview_combo.currentText())
        self._update_road_preview_mode(
            2, self.camera_feeds.headlight_secondary.preview_combo.currentText())
        self.headlight_thread.start()
        self._refresh_calibration_controls()

    def _stop_headlight_detection(self):
        self._headlight_camera_available = False
        self._road_position_ready = False
        if self.headlight_thread is not None:
            self.headlight_thread.stop()
            if self.headlight_thread.isRunning():
                self.controls.stereo_status.setText(
                    "Waiting for the road camera driver to release; try Stop again shortly.")
                return False
            self.headlight_thread.deleteLater()
            self.headlight_thread = None
        return True

    def _on_headlight_lost(self):
        self.diagnostics.record_event("road_lights_lost")
        self._road_position_ready = False
        self.tracker.on_lights_lost()
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
        if self.headlight_thread is not None:
            self.headlight_thread.update_detection_settings(
                self.controls.get_light_detection_settings())

    def _capture_light_background(self):
        if self.headlight_thread is None or not self.headlight_thread.isRunning():
            self.controls.set_background_status(
                "Start Standby first, remove the phone/test light, then capture.")
            return
        self.controls.check_background_rejection.setChecked(True)
        self.controls.set_background_status(
            "Waiting for the next camera frame — keep the test light off...")
        self.headlight_thread.capture_background()

    def _clear_light_background(self):
        if self.headlight_thread is not None:
            self.headlight_thread.clear_background()
        else:
            self.controls.set_background_status(
                "Background reference cleared")

    def _activate_phone_light_diagnostics(self):
        """Make the phone preset immediately observable and remove stale gates."""

        self.camera_feeds.headlight.preview_combo.setCurrentText(
            "Detection overlay")
        if self.headlight_thread is not None:
            self.headlight_thread.clear_background()
        self._update_detection_settings()

    def _on_camera_controls_report(self, report):
        if not report:
            return
        actual = report.get("actual", {})
        accepted = report.get("accepted", {})
        if not report.get("enabled"):
            text = (
                "Camera controls OFF — automatic exposure restored. "
                f"Camera reports exposure {actual.get('exposure', 0):g}."
            )
        elif report.get("auto_exposure_requested"):
            text = (
                "Camera readback — auto exposure ON; "
                f"brightness {actual.get('brightness', 0):g}, "
                f"contrast {actual.get('contrast', 0):g}, "
                f"gain {actual.get('gain', 0):g}."
            )
        else:
            exposure_ok = accepted.get("exposure", False)
            text = (
                "Camera readback — exposure requested "
                f"{report.get('exposure_requested', 0):g}, camera reports "
                f"{actual.get('exposure', 0):g} "
                f"({'accepted' if exposure_ok else 'driver rejected'}); "
                f"brightness {actual.get('brightness', 0):g}, "
                f"contrast {actual.get('contrast', 0):g}, "
                f"gain {actual.get('gain', 0):g}."
            )
        self.controls.set_camera_control_feedback(text)

    def _update_road_preview_mode(self, camera_number, preview_mode):
        if isinstance(self.headlight_thread, HeadlightDetectorThread):
            self.headlight_thread.set_preview_mode(
                preview_mode, camera_number=camera_number)
        elif (isinstance(
                self.headlight_thread, MonocularHeadlightDetectorThread)
                and camera_number == 1):
            self.headlight_thread.set_preview_mode(preview_mode)

    def _open_guided_calibration(self):
        previous_state = self._session_state
        previous_mode = self.controls.combo_operating_mode.currentText()
        previous_setup = self.controls.combo_detection_setup.currentText()
        driver_index = self.controls.spin_driver_camera.value()
        road_index = self.controls.spin_headlight_camera.value()
        if driver_index == road_index:
            QMessageBox.warning(
                self,
                "Camera index conflict",
                "Guided calibration needs two independent feeds. Set the driver "
                "camera to 0 and the USB road camera to 1, then try again.",
            )
            return

        # Calibration is a temporary preparation workflow: both single-camera
        # previews are opened, while normal intersection calculations remain paused.
        self._set_session_state(SessionState.STANDBY)
        if self.controls.combo_operating_mode.currentText() != OperatingMode.FULLY_AUTO.value:
            self.controls.combo_operating_mode.setCurrentText(
                OperatingMode.FULLY_AUTO.value)
        if self.controls.combo_detection_setup.currentText() != "Single Camera":
            self.controls.combo_detection_setup.setCurrentText("Single Camera")
        self._ensure_required_cameras()

        if not isinstance(self.headlight_thread, MonocularHeadlightDetectorThread):
            QMessageBox.warning(
                self,
                "Road camera unavailable",
                "The single road-camera worker could not be started. Check camera "
                "index 1 and close other applications using the webcam.",
            )
            self._restore_after_calibration(
                previous_state, previous_mode, previous_setup)
            return

        wizard = GuidedCalibrationWizard(
            self.cap_thread,
            self.headlight_thread,
            driver_camera_index=driver_index,
            road_camera_index=road_index,
            parent=self,
        )
        try:
            if wizard.exec_() == GuidedCalibrationWizard.Accepted:
                self._driver_depth_calibration = wizard.driver_calibration
                self._road_range_calibration = wizard.road_calibration
                self.controls.spin_brightness_threshold.setValue(
                    self._road_range_calibration.brightness_threshold)
                self.cap_thread.set_calibration(
                    self._driver_depth_calibration.as_intrinsic_calibration())
                self.headlight_thread.set_range_calibration(
                    self._road_range_calibration
                    if wizard.activate_road_range else None)
                self.controls.check_driver_depth_calibration.setChecked(
                    wizard.activate_driver_depth)
                self.controls.check_road_range_calibration.setChecked(
                    wizard.activate_road_range)
                self._calibration_options_changed()
        finally:
            self._restore_after_calibration(
                previous_state, previous_mode, previous_setup)

    def _restore_after_calibration(self, state, mode, setup):
        self._stop_headlight_detection()
        self.controls.combo_operating_mode.blockSignals(True)
        self.controls.combo_detection_setup.blockSignals(True)
        self.controls.combo_operating_mode.setCurrentText(mode)
        self.controls.combo_detection_setup.setCurrentText(setup)
        self.controls.combo_operating_mode.blockSignals(False)
        self.controls.combo_detection_setup.blockSignals(False)
        self.controls._update_mode_controls()
        self._set_session_state(state)
        self._refresh_calibration_controls()

    def _refresh_calibration_controls(self):
        driver_index = self.controls.spin_driver_camera.value()
        road_index = self.controls.spin_headlight_camera.value()
        driver_valid = (
            self._driver_depth_calibration is not None
            and self._driver_depth_calibration.camera_index == driver_index)
        road_valid = (
            self._road_range_calibration is not None
            and self._road_range_calibration.camera_index == road_index)

        driver_box = self.controls.check_driver_depth_calibration
        road_box = self.controls.check_road_range_calibration
        policy = self.controls.mode_policy()
        single_road = not self.controls.is_stereo_detection()
        driver_box.setEnabled(driver_valid and policy.use_driver_camera)
        road_box.setEnabled(
            road_valid and policy.use_road_camera and single_road)
        if not driver_valid:
            driver_box.setChecked(False)
        if not road_valid:
            road_box.setChecked(False)

        driver_text = "driver ready" if driver_valid else "driver not calibrated"
        road_text = "road ready" if road_valid else "road not calibrated"
        self.controls.calibration_status.setText(
            f"Camera {driver_index}: {driver_text} · Camera {road_index}: {road_text}")

    def _calibration_options_changed(self):
        if self.cap_thread.isRunning():
            self._push_config()
        if isinstance(self.headlight_thread, MonocularHeadlightDetectorThread):
            calibration = (
                self._road_range_calibration
                if self.controls.check_road_range_calibration.isChecked()
                else None)
            if (calibration is not None
                    and self.controls.spin_brightness_threshold.value()
                    != calibration.brightness_threshold):
                self.controls.spin_brightness_threshold.setValue(
                    calibration.brightness_threshold)
            self.headlight_thread.set_range_calibration(calibration)

    def _push_config(self):
        profile = self._driver_depth_calibration
        use_calibration = (
            profile is not None
            and profile.camera_index == self.controls.spin_driver_camera.value()
            and self.controls.check_driver_depth_calibration.isChecked())
        camera_x, camera_y, camera_z = self.controls.get_camera_pos()
        self.cap_thread.update_config(TrackingConfig(
            screen_w_cm=self.controls.spin_ws_w.value(),
            screen_h_cm=self.controls.spin_ws_h.value(),
            eye_dist_cm=self.controls.spin_eye_dist.value(),
            camera_x_cm=camera_x,
            camera_y_cm=camera_y,
            camera_z_cm=camera_z,
            ipd_cm=profile.ipd_cm if profile is not None else 6.3,
            use_calibration=use_calibration,
        ))

    def _on_params_changed(self):
        self._refresh_lcd_configuration()
        if self.cap_thread.isRunning():
            self._push_config()
        self.tracker.on_params_changed(
            calculate=self._coordinates_ready_for_calculation())
        self._update_single_projection()

    def _toggle_movement(self, playing):
        if (playing and (
                not calculations_enabled(self._session_state)
                or not self.controls.mode_policy().manual_headlight)):
            self._stop_movement_simulation()
            return
        if playing:
            self.controls.btn_play_movement.setText("Stop Light Movement")
            self.controls.btn_play_movement.setIcon(IconFactory.icon("stop"))
            self.tracker.start_movement()
            self._movement_timer.start()
        else:
            self._movement_timer.stop()
            self.tracker.stop_movement()
            self.controls.btn_play_movement.setText("Play Light Movement")
            self.controls.btn_play_movement.setIcon(IconFactory.icon("play"))
            self.tracker.on_params_changed(
                calculate=self._coordinates_ready_for_calculation())

    def _reset_3d_view(self):
        self.scene_3d.gl_view.setCameraPosition(distance=145, elevation=22, azimuth=-45)

    # ── responsive layout ───────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 1180
        self.main_splitter.setOrientation(Qt.Vertical if narrow else Qt.Horizontal)
        if narrow:
            self.sidebar.setMinimumWidth(0)
            self.sidebar.setMaximumWidth(16777215)
        else:
            self.sidebar.setMinimumWidth(380)
            self.sidebar.setMaximumWidth(500)

    # ── clean shutdown ──────────────────────────────────────────────

    def closeEvent(self, event):
        self._movement_timer.stop()
        self.lcd_blocker.disable_output()
        if self.diagnostics.is_active:
            self.diagnostics.record_event("application_closing")
            self.diagnostics.stop()
        if (self._camera_discovery_thread is not None
                and self._camera_discovery_thread.isRunning()):
            self._camera_discovery_thread.requestInterruption()
            self._camera_discovery_thread.wait(5000)
            if self._camera_discovery_thread.isRunning():
                event.ignore()
                return
        self.cap_thread.stop()
        self._stop_headlight_detection()
        if (self.cap_thread.isRunning()
                or (self.headlight_thread is not None and self.headlight_thread.isRunning())):
            event.ignore()
            return
        event.accept()

    # ── helpers ──────────────────────────────────────────────────────

    def _set_initial_geometry(self):
        """Open centered at a useful size without covering the full desktop."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1400, 850)
            return
        available = screen.availableGeometry()
        minimum_width = min(960, available.width())
        minimum_height = min(640, available.height())
        self.setMinimumSize(minimum_width, minimum_height)
        width = min(1600, max(minimum_width, int(available.width() * 0.88)))
        height = min(960, max(minimum_height, int(available.height() * 0.88)))
        width = min(width, available.width())
        height = min(height, available.height())
        self.resize(width, height)
        self.move(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
        )

    @staticmethod
    def _application_icon():
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return QIcon(os.path.join(base, "assets", "glaretracker-icon.ico"))
