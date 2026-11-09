"""User-configurable controls panel (windshield, camera, light, vehicle)."""

from PyQt5.QtCore import Qt, pyqtSignal

from PyQt5.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QFormLayout, QLabel,
    QPushButton, QDoubleSpinBox, QComboBox, QSpinBox, QSizePolicy, QCheckBox,
    QLineEdit,
)

from glare_tracker.widgets.icons import ICON_SIZE, IconFactory
from glare_tracker.operating_modes import OperatingMode, policy_for
from glare_tracker.headlight_detector import LightDetectionSettings
from glare_tracker.drowsiness import DrowsinessSettings


class CameraSelector(QComboBox):
    """Dropdown that exposes a spin-box-compatible camera-index API."""

    valueChanged = pyqtSignal(int)

    def __init__(self, default_index=0, parent=None):
        super().__init__(parent)
        self._fallback_value = int(default_index)
        self.setMinimumHeight(30)
        self.addItem(f"Camera {default_index} (not scanned)", default_index)
        self.currentIndexChanged.connect(self._emit_value_changed)

    def value(self):
        value = self.currentData()
        return self._fallback_value if value is None else int(value)

    def setValue(self, camera_index):
        camera_index = int(camera_index)
        self._fallback_value = camera_index
        item_index = self.findData(camera_index)
        if item_index < 0:
            self.addItem(f"Camera {camera_index} (unavailable)", camera_index)
            item_index = self.count() - 1
        self.setCurrentIndex(item_index)

    def set_available_cameras(self, devices):
        previous = self.value()
        self.blockSignals(True)
        self.clear()
        for device in devices:
            camera_index = int(device.index)
            label = (
                f"Camera {camera_index}"
                + (f" — {device.name}" if getattr(device, "name", "") else "")
                + f" — {device.width}×{device.height} "
                f"({device.backend})"
            )
            self.addItem(label, camera_index)
        if self.count():
            selected = self.findData(previous)
            self.setCurrentIndex(selected if selected >= 0 else 0)
            self._fallback_value = int(self.currentData())
            self.setEnabled(True)
        else:
            self.addItem("No available cameras detected", None)
            self.setEnabled(False)
        self.blockSignals(False)
        if self.isEnabled():
            self.valueChanged.emit(self.value())

    def _emit_value_changed(self):
        if self.currentData() is not None:
            self._fallback_value = int(self.currentData())
            self.valueChanged.emit(self._fallback_value)


class ControlsPanel(QWidget):
    """Sidebar panel with all user-configurable tracking parameters.

    Uses a flat QWidget (not nested QGroupBox) for cleaner rendering
    inside the OperationsSidebar tab.
    """

    drowsiness_settings_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Operating mode is the primary workflow choice. It replaces the old
        # independent Manual/Auto light switch, which allowed contradictory
        # combinations of driver and road inputs.
        self.mode_group = QGroupBox("Operating Mode")
        self.mode_group.setProperty("section", "vision")
        mode_layout = QVBoxLayout(self.mode_group)
        mode_layout.setSpacing(6)
        self.combo_operating_mode = QComboBox()
        self.combo_operating_mode.addItems([mode.value for mode in OperatingMode])
        self.mode_description = QLabel()
        self.mode_description.setObjectName("mutedText")
        self.mode_description.setWordWrap(True)
        self.check_show_advanced_configuration = QCheckBox(
            "Show advanced and experimental configuration")
        mode_layout.addWidget(self.combo_operating_mode)
        mode_layout.addWidget(self.mode_description)
        mode_layout.addWidget(self.check_show_advanced_configuration)
        layout.addWidget(self.mode_group)

        # ── Windshield ──
        self.ws_group = QGroupBox("Windshield")
        self.ws_group.setProperty("section", "geometry")
        ws_layout = QFormLayout(self.ws_group)
        ws_layout.setSpacing(6)
        self._configure_form(ws_layout)
        self.spin_ws_w = self._make_spin(1.0, 500.0, 34.5, " cm")
        self.spin_ws_h = self._make_spin(1.0, 500.0, 19.5, " cm")
        ws_layout.addRow("Width:", self.spin_ws_w)
        ws_layout.addRow("Height:", self.spin_ws_h)
        layout.addWidget(self.ws_group)

        # ── Camera position ──
        self.camera_group = QGroupBox("Camera Position")
        self.camera_group.setProperty("section", "camera")
        camera_layout = QFormLayout(self.camera_group)
        camera_layout.setSpacing(6)
        self._configure_form(camera_layout)
        self.spin_camera_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_y = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_z = self._make_spin(-1000, 1000, 19.5, " cm")
        camera_layout.addRow("X:", self.spin_camera_x)
        camera_layout.addRow("Y:", self.spin_camera_y)
        camera_layout.addRow("Z:", self.spin_camera_z)
        layout.addWidget(self.camera_group)

        # ── Driver distance ──
        self.dist_group = QGroupBox("Tracked Driver Reference")
        self.dist_group.setProperty("section", "driver")
        dist_layout = QFormLayout(self.dist_group)
        dist_layout.setSpacing(6)
        self._configure_form(dist_layout)
        self.spin_eye_dist = self._make_spin(5.0, 500.0, 50.0, " cm")
        self.distance_note = QLabel("Manual / reference measurement")
        self.distance_note.setObjectName("mutedText")
        dist_layout.addRow("Distance:", self.spin_eye_dist)
        dist_layout.addRow(self.distance_note)
        layout.addWidget(self.dist_group)

        # Manual driver position for Fully Manual and Driver Position Fixed.
        self.manual_driver_group = QGroupBox("Manual Driver Position")
        self.manual_driver_group.setProperty("section", "driver")
        driver_layout = QFormLayout(self.manual_driver_group)
        driver_layout.setSpacing(6)
        self._configure_form(driver_layout)
        self.spin_driver_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_driver_y = self._make_spin(-1000, -1.0, -50.0, " cm")
        self.spin_driver_z = self._make_spin(-1000, 1000, 9.75, " cm")
        driver_layout.addRow("X:", self.spin_driver_x)
        driver_layout.addRow("Y:", self.spin_driver_y)
        driver_layout.addRow("Z:", self.spin_driver_z)
        layout.addWidget(self.manual_driver_group)

        # ── Guided distance calibration ──
        self.calibration_group = QGroupBox("Single-Camera Calibration")
        self.calibration_group.setProperty("section", "vision")
        calibration_layout = QVBoxLayout(self.calibration_group)
        calibration_layout.setSpacing(6)
        self.btn_guided_calibration = QPushButton(
            "Calibrate Single-Camera Distances")
        self.btn_guided_calibration.setIcon(IconFactory.icon("target"))
        self.btn_guided_calibration.setIconSize(ICON_SIZE)
        self.btn_guided_calibration.setMinimumHeight(34)
        self.check_driver_depth_calibration = QCheckBox(
            "Use estimated driver depth")
        self.check_road_range_calibration = QCheckBox(
            "Use estimated road-light range")
        self.calibration_status = QLabel("No guided calibration loaded")
        self.calibration_status.setWordWrap(True)
        self.calibration_status.setObjectName("mutedText")
        calibration_layout.addWidget(self.btn_guided_calibration)
        calibration_layout.addWidget(self.check_driver_depth_calibration)
        calibration_layout.addWidget(self.check_road_range_calibration)
        calibration_layout.addWidget(self.calibration_status)
        layout.addWidget(self.calibration_group)

        # ── Vehicle / light mode ──
        self.vehicle_group = QGroupBox("Vehicle Type")
        self.vehicle_group.setProperty("section", "vehicle")
        vehicle_layout = QFormLayout(self.vehicle_group)
        vehicle_layout.setSpacing(6)
        self._configure_form(vehicle_layout)
        self.combo_vehicle = QComboBox()
        self.combo_vehicle.addItems(["Motorcycle", "Four-Wheeler/Car", "Extreme Vehicle"])
        vehicle_layout.addRow("Category:", self.combo_vehicle)
        layout.addWidget(self.vehicle_group)

        # ── Headlight source ──
        self.light_group = QGroupBox("Manual Headlight Position")
        self.light_group.setProperty("section", "light")
        light_layout = QFormLayout(self.light_group)
        light_layout.setSpacing(6)
        self._configure_form(light_layout)
        self.spin_light_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_light_y = self._make_spin(-1000, 1000, 120.0, " cm")
        self.spin_light_z = self._make_spin(-1000, 5000, 10.0, " cm")
        light_layout.addRow("X:", self.spin_light_x)
        light_layout.addRow("Y:", self.spin_light_y)
        light_layout.addRow("Z:", self.spin_light_z)
        layout.addWidget(self.light_group)

        # Camera roles remain assignable even while a role is inactive. This
        # allows Camera 0 to detect a lamp while driver coordinates are fixed.
        self.auto_camera_group = QGroupBox("Camera Selection")
        self.auto_camera_group.setProperty("section", "vision")
        auto_layout = QFormLayout(self.auto_camera_group)
        auto_layout.setSpacing(6)
        self._configure_form(auto_layout)
        self.combo_detection_setup = QComboBox()
        self.combo_detection_setup.addItems(["Single Camera", "Stereo Cameras"])
        self.combo_detection_setup.setCurrentText("Stereo Cameras")
        # Current replacement-camera installation: DirectShow enumerates the
        # integrated laptop camera first and the identical USB pair next.
        # Discovery corrects this automatically by device name if indices move.
        self.spin_driver_camera = self._make_index_spin(0)
        self.spin_headlight_camera = self._make_index_spin(1)
        self.spin_headlight_camera_2 = self._make_index_spin(2)
        self.check_lock_driver_camera = QCheckBox(
            "Lock integrated camera as driver")
        self.check_lock_driver_camera.setChecked(True)
        self.check_lock_driver_camera.setToolTip(
            "Discovery assigns the Integrated Camera only to the driver role "
            "and excludes it from road-stereo calibration.")
        self.spin_single_depth = self._make_spin(10.0, 5000.0, 120.0, " cm")
        self.spin_camera_hfov = self._make_spin(10.0, 170.0, 70.0, " deg")
        self.spin_brightness_threshold = QSpinBox()
        self.spin_brightness_threshold.setRange(0, 255)
        self.spin_brightness_threshold.setValue(200)
        self.spin_brightness_threshold.setMinimumHeight(30)
        self.spin_brightness_threshold.setToolTip(
            "In adaptive mode this is a ceiling; scene brightness chooses the "
            "lower working threshold shown on the feed")
        self.btn_refresh_cameras = QPushButton("Refresh Available Cameras")
        self.btn_refresh_cameras.setIcon(IconFactory.icon("reset"))
        self.btn_refresh_cameras.setIconSize(ICON_SIZE)
        self.btn_refresh_cameras.setMinimumHeight(34)
        self.camera_scan_status = QLabel(
            "Choose which detected camera is used for each role.")
        self.camera_scan_status.setWordWrap(True)
        self.camera_scan_status.setObjectName("mutedText")
        self.auto_note = QLabel()
        self.auto_note.setWordWrap(True)
        self.auto_note.setObjectName("mutedText")
        auto_layout.addRow("Setup:", self.combo_detection_setup)
        auto_layout.addRow(self.check_lock_driver_camera)
        auto_layout.addRow("Driver camera:", self.spin_driver_camera)
        auto_layout.addRow("Road LEFT camera:", self.spin_headlight_camera)
        auto_layout.addRow("Road RIGHT camera:", self.spin_headlight_camera_2)
        auto_layout.addRow("Assumed depth:", self.spin_single_depth)
        auto_layout.addRow("Camera HFOV:", self.spin_camera_hfov)
        auto_layout.addRow(self.btn_refresh_cameras)
        auto_layout.addRow(self.camera_scan_status)
        auto_layout.addRow(self.auto_note)
        self.btn_stereo_calibration = QPushButton("Calibrate road stereo (chessboard)")
        self.stereo_status = QLabel("Calibration required before stereo depth is available.")
        self.stereo_status.setWordWrap(True)
        auto_layout.addRow(self.btn_stereo_calibration)
        auto_layout.addRow(self.stereo_status)
        layout.addWidget(self.auto_camera_group)

        # Driver monitoring reuses the existing Face Mesh result.  It remains
        # disabled by default because its thresholds have not yet been
        # validated as a safety device for this camera or vehicle environment.
        self.driver_monitoring_group = QGroupBox(
            "Driver Drowsiness Monitoring (Experimental)")
        self.driver_monitoring_group.setProperty("section", "driver")
        drowsiness_layout = QFormLayout(self.driver_monitoring_group)
        drowsiness_layout.setSpacing(6)
        self._configure_form(drowsiness_layout)
        self.check_drowsiness = QCheckBox("Enable drowsiness indicators")
        self.combo_drowsiness_profile = QComboBox()
        self.combo_drowsiness_profile.addItems(["Default", "Custom"])
        self.spin_eye_openness = self._make_spin(
            0.05, 0.60, 0.21, " ratio")
        self.spin_eye_openness.setDecimals(2)
        self.spin_eye_openness.setSingleStep(0.01)
        self.spin_blink_duration = QSpinBox()
        self.spin_blink_duration.setRange(100, 5000)
        self.spin_blink_duration.setValue(800)
        self.spin_blink_duration.setSuffix(" ms")
        self.spin_blink_duration.setMinimumHeight(30)
        self.spin_perclos_threshold = self._make_spin(
            1.0, 95.0, 25.0, " %")
        self.spin_perclos_threshold.setDecimals(0)
        self.spin_perclos_window = self._make_spin(
            5.0, 300.0, 60.0, " s")
        self.spin_perclos_window.setDecimals(0)
        self.spin_yawn_openness = self._make_spin(
            0.05, 1.50, 0.35, " ratio")
        self.spin_yawn_openness.setDecimals(2)
        self.spin_yawn_openness.setSingleStep(0.01)
        self.spin_yawn_duration = QSpinBox()
        self.spin_yawn_duration.setRange(250, 10000)
        self.spin_yawn_duration.setValue(1500)
        self.spin_yawn_duration.setSuffix(" ms")
        self.spin_yawn_duration.setMinimumHeight(30)
        self.drowsiness_status = QLabel(
            "Off. Experimental research indicator; not a safety-certified alarm.")
        self.drowsiness_status.setObjectName("mutedText")
        self.drowsiness_status.setWordWrap(True)
        drowsiness_layout.addRow(self.check_drowsiness)
        drowsiness_layout.addRow("Threshold profile:", self.combo_drowsiness_profile)
        drowsiness_layout.addRow("Eye openness minimum:", self.spin_eye_openness)
        drowsiness_layout.addRow("Long closure duration:", self.spin_blink_duration)
        drowsiness_layout.addRow("PERCLOS warning:", self.spin_perclos_threshold)
        drowsiness_layout.addRow("PERCLOS window:", self.spin_perclos_window)
        drowsiness_layout.addRow("Yawn openness minimum:", self.spin_yawn_openness)
        drowsiness_layout.addRow("Yawn duration:", self.spin_yawn_duration)
        drowsiness_layout.addRow(self.drowsiness_status)
        layout.addWidget(self.driver_monitoring_group)

        self.check_drowsiness.toggled.connect(
            self._drowsiness_controls_changed)
        self.combo_drowsiness_profile.currentTextChanged.connect(
            self._drowsiness_controls_changed)
        for widget in (
            self.spin_eye_openness,
            self.spin_blink_duration,
            self.spin_perclos_threshold,
            self.spin_perclos_window,
            self.spin_yawn_openness,
            self.spin_yawn_duration,
        ):
            widget.valueChanged.connect(self._emit_drowsiness_settings)

        # Camera-driver controls and software image-processing controls are
        # intentionally grouped together so the operator can tune a new lamp
        # while watching the selectable processing previews above the feed.
        self.light_detection_group = QGroupBox("Light Detection")
        self.light_detection_group.setProperty("section", "light")
        detection_layout = QFormLayout(self.light_detection_group)
        detection_layout.setSpacing(6)
        self._configure_form(detection_layout)

        self.check_apply_camera_controls = QCheckBox(
            "Apply camera controls")
        self.check_auto_exposure = QCheckBox("Use auto exposure")
        self.check_auto_exposure.setChecked(True)
        self.spin_exposure = self._make_spin(-13.0, 1.0, -6.0)
        self.spin_exposure.setSingleStep(1.0)
        self.spin_camera_brightness = self._make_spin(0.0, 255.0, 128.0)
        self.spin_camera_brightness.setSingleStep(1.0)
        self.spin_camera_contrast = self._make_spin(0.0, 255.0, 128.0)
        self.spin_camera_contrast.setSingleStep(1.0)
        self.spin_camera_gain = self._make_spin(0.0, 255.0, 0.0)
        self.spin_camera_gain.setSingleStep(1.0)
        self.camera_control_feedback = QLabel(
            "Camera controls OFF — the values above are not sent to the camera.")
        self.camera_control_feedback.setObjectName("mutedText")
        self.camera_control_feedback.setWordWrap(True)

        self.check_background_rejection = QCheckBox(
            "Reject captured background")
        self.spin_background_difference = QSpinBox()
        self.spin_background_difference.setRange(1, 255)
        self.spin_background_difference.setValue(30)
        self.spin_background_difference.setMinimumHeight(30)
        self.btn_capture_background = QPushButton(
            "Capture Background Without Test Light")
        self.btn_capture_background.setMinimumHeight(34)
        self.btn_clear_background = QPushButton("Clear Background Reference")
        self.btn_clear_background.setMinimumHeight(32)
        self.background_status = QLabel(
            "No background captured. Start Standby, remove the phone light, "
            "then capture the static scene.")
        self.background_status.setObjectName("mutedText")
        self.background_status.setWordWrap(True)

        self.check_local_contrast = QCheckBox(
            "Require multi-scale light saliency")
        self.check_local_contrast.setChecked(True)
        self.spin_local_contrast_threshold = QSpinBox()
        self.spin_local_contrast_threshold.setRange(1, 255)
        self.spin_local_contrast_threshold.setValue(8)
        self.spin_local_contrast_threshold.setMinimumHeight(30)
        self.spin_local_contrast_threshold.setToolTip(
            "Minimum multi-scale contrast response required for a light")
        self.spin_min_source_confidence = self._make_spin(
            0.0, 100.0, 25.0, " %")
        self.spin_min_source_confidence.setDecimals(0)
        self.spin_min_source_confidence.setToolTip(
            "Reject candidates whose combined saliency, brightness, shape, "
            "and saturated-core score is below this percentage")
        self.btn_daylight_phone_preset = QPushButton(
            "Load Daylight Phone-Light Preset")
        self.btn_daylight_phone_preset.setMinimumHeight(34)

        self.btn_stable_stereo_preset = QPushButton(
            "Current Rig - Smooth Preset")
        self.btn_stable_stereo_preset.setMinimumHeight(34)
        self.btn_stable_stereo_preset.setToolTip(
            "Load the exact values that produced stable tracking on the current rig. "
            "This favors stability over distant-light coverage.")
        self.btn_balanced_stereo_preset = QPushButton(
            "Balanced Stereo Coverage Preset")
        self.btn_balanced_stereo_preset.setMinimumHeight(34)
        self.btn_balanced_stereo_preset.setToolTip(
            "Use moderate spatial filtering with temporal confirmation so smaller "
            "lights remain detectable.")
        self.check_show_advanced_detection = QCheckBox(
            "Show advanced detector tuning")
        self.detection_summary = QLabel()
        self.detection_summary.setObjectName("mutedText")
        self.detection_summary.setWordWrap(True)

        self.check_adaptive_threshold = QCheckBox(
            "Adapt threshold to scene")
        self.check_adaptive_threshold.setChecked(True)
        self.spin_min_light_area = self._make_spin(
            1.0, 100000.0, 5.0, " px")
        self.spin_min_light_area.setDecimals(0)
        self.spin_max_light_area = self._make_spin(
            2.0, 500000.0, 50000.0, " px")
        self.spin_max_light_area.setDecimals(0)
        self.combo_blur_size = QComboBox()
        self.combo_blur_size.addItems([
            "None", "3 x 3", "5 x 5", "7 x 7", "9 x 9",
        ])
        self.combo_blur_size.setCurrentText("3 x 3")
        self.spin_morphology_iterations = QSpinBox()
        self.spin_morphology_iterations.setRange(0, 5)
        self.spin_morphology_iterations.setValue(1)
        self.spin_morphology_iterations.setMinimumHeight(30)
        self.spin_max_light_sources = QSpinBox()
        self.spin_max_light_sources.setRange(1, 8)
        self.spin_max_light_sources.setValue(4)
        self.spin_max_light_sources.setMinimumHeight(30)
        self.spin_light_match_distance = self._make_spin(
            5.0, 500.0, 80.0, " px")
        self.spin_light_match_distance.setDecimals(0)
        self.btn_reset_light_detection = QPushButton("Reset Detection Defaults")
        self.btn_reset_light_detection.setMinimumHeight(32)
        self.detection_note = QLabel(
            "Multi-scale saliency compares each bright patch with eight "
            "surrounding patches at six sizes, so nearby and distant lamps "
            "share one detector. Confidence rejects weak clutter. Capturing "
            "the unchanged scene provides an additional optional check."
        )
        self.detection_note.setObjectName("mutedText")
        self.detection_note.setWordWrap(True)

        detection_layout.addRow(self.btn_stable_stereo_preset)
        detection_layout.addRow(self.btn_balanced_stereo_preset)
        detection_layout.addRow(self.check_show_advanced_detection)
        detection_layout.addRow(self.detection_summary)
        detection_layout.addRow(self.check_apply_camera_controls)
        detection_layout.addRow(self.check_auto_exposure)
        detection_layout.addRow("Exposure:", self.spin_exposure)
        detection_layout.addRow("Camera brightness:", self.spin_camera_brightness)
        detection_layout.addRow("Camera contrast:", self.spin_camera_contrast)
        detection_layout.addRow("Camera gain:", self.spin_camera_gain)
        detection_layout.addRow(self.camera_control_feedback)
        detection_layout.addRow(self.check_background_rejection)
        detection_layout.addRow(
            "Change threshold:", self.spin_background_difference)
        detection_layout.addRow(self.btn_capture_background)
        detection_layout.addRow(self.btn_clear_background)
        detection_layout.addRow(self.background_status)
        detection_layout.addRow(self.check_local_contrast)
        detection_layout.addRow(
            "Saliency floor:", self.spin_local_contrast_threshold)
        detection_layout.addRow(
            "Minimum source confidence:", self.spin_min_source_confidence)
        detection_layout.addRow(self.check_adaptive_threshold)
        detection_layout.addRow(
            "Brightness threshold:", self.spin_brightness_threshold)
        detection_layout.addRow("Minimum light area:", self.spin_min_light_area)
        detection_layout.addRow("Maximum light area:", self.spin_max_light_area)
        detection_layout.addRow("Gaussian blur:", self.combo_blur_size)
        detection_layout.addRow(
            "Noise cleanup passes:", self.spin_morphology_iterations)
        detection_layout.addRow("Maximum sources:", self.spin_max_light_sources)
        detection_layout.addRow(
            "ID matching distance:", self.spin_light_match_distance)
        detection_layout.addRow(self.btn_daylight_phone_preset)
        detection_layout.addRow(self.btn_reset_light_detection)
        detection_layout.addRow(self.detection_note)
        layout.addWidget(self.light_detection_group)

        self.combo_operating_mode.currentTextChanged.connect(self._update_mode_controls)
        self.combo_detection_setup.currentTextChanged.connect(self._update_auto_controls)
        self.check_apply_camera_controls.toggled.connect(
            self._update_detection_control_states)
        self.check_auto_exposure.toggled.connect(
            self._update_detection_control_states)
        self.check_background_rejection.toggled.connect(
            self._update_detection_control_states)
        self.check_local_contrast.toggled.connect(
            self._update_detection_control_states)
        self.spin_min_light_area.valueChanged.connect(
            self._minimum_light_area_changed)
        self.spin_max_light_area.valueChanged.connect(
            self._maximum_light_area_changed)
        self.btn_reset_light_detection.clicked.connect(
            self.reset_light_detection_defaults)
        self.btn_daylight_phone_preset.clicked.connect(
            self.load_daylight_phone_preset)
        self.btn_stable_stereo_preset.clicked.connect(
            self.load_stable_stereo_preset)
        self.btn_balanced_stereo_preset.clicked.connect(
            self.load_balanced_stereo_preset)
        self.check_show_advanced_detection.toggled.connect(
            self._update_detection_advanced_visibility)
        for widget in (
            self.spin_local_contrast_threshold,
            self.spin_min_source_confidence,
            self.spin_brightness_threshold,
            self.spin_min_light_area,
            self.spin_max_light_area,
            self.spin_morphology_iterations,
            self.spin_max_light_sources,
            self.spin_light_match_distance,
        ):
            widget.valueChanged.connect(self._refresh_detection_summary)
        for widget in (
            self.check_adaptive_threshold,
            self.check_local_contrast,
        ):
            widget.toggled.connect(self._refresh_detection_summary)
        self.combo_blur_size.currentTextChanged.connect(
            self._refresh_detection_summary)

        # ── Light movement ──
        movement_group = QGroupBox("Simulation")
        self.movement_group = movement_group
        movement_group.setProperty("section", "simulation")
        movement_layout = QVBoxLayout(movement_group)
        movement_layout.setSpacing(6)
        self.combo_movement = QComboBox()
        self.combo_movement.addItems([
            "Coming straight",
            "Coming at the opposite side",
            "Long distance",
        ])
        self.btn_play_movement = QPushButton("Play Light Movement")
        self.btn_play_movement.setObjectName("simulationAction")
        self.btn_play_movement.setIcon(IconFactory.icon("play"))
        self.btn_play_movement.setIconSize(ICON_SIZE)
        self.btn_play_movement.setCheckable(True)
        self.btn_play_movement.setMinimumHeight(34)
        movement_layout.addWidget(self.combo_movement)
        movement_layout.addWidget(self.btn_play_movement)
        layout.addWidget(movement_group)

        # ── Research diagnostics ──
        self.diagnostics_group = QGroupBox("Research Recording")
        self.diagnostics_group.setProperty("section", "vision")
        diagnostics_layout = QVBoxLayout(self.diagnostics_group)
        diagnostics_layout.setSpacing(6)
        self.check_record_diagnostics = QCheckBox(
            "Record timestamped CSV and camera video"
        )
        self.check_record_diagnostics.setToolTip(
            "Write telemetry.csv, per-frame video timestamps, session metadata, "
            "and available camera previews to a diagnostics session folder"
        )
        self.diagnostics_status = QLabel("Recording is off")
        self.diagnostics_status.setObjectName("mutedText")
        self.diagnostics_status.setWordWrap(True)
        diagnostics_layout.addWidget(self.check_record_diagnostics)
        diagnostics_layout.addWidget(self.diagnostics_status)

        marker_form = QFormLayout()
        self.combo_ground_truth_target = QComboBox()
        self.combo_ground_truth_target.addItems(
            ["Driver Eye Midpoint", "Road Light", "Windshield Intersection"]
        )
        self.edit_ground_truth_label = QLineEdit()
        self.edit_ground_truth_label.setPlaceholderText("e.g. driver-D50-X0-R1")
        self.spin_ground_truth_x = self._make_spin(-5000, 5000, 0.0, " cm")
        self.spin_ground_truth_y = self._make_spin(-5000, 5000, -50.0, " cm")
        self.spin_ground_truth_z = self._make_spin(-5000, 5000, 9.75, " cm")
        self.btn_mark_ground_truth = QPushButton("Mark Measured Position")
        self.btn_mark_ground_truth.setMinimumHeight(32)
        self.ground_truth_status = QLabel(
            "Start recording, enter tape-measured coordinates, then mark each "
            "stable test position."
        )
        self.ground_truth_status.setObjectName("mutedText")
        self.ground_truth_status.setWordWrap(True)
        marker_form.addRow("Target:", self.combo_ground_truth_target)
        marker_form.addRow("Condition ID:", self.edit_ground_truth_label)
        marker_form.addRow("Measured X:", self.spin_ground_truth_x)
        marker_form.addRow("Measured Y:", self.spin_ground_truth_y)
        marker_form.addRow("Measured Z:", self.spin_ground_truth_z)
        marker_form.addRow(self.btn_mark_ground_truth)
        marker_form.addRow(self.ground_truth_status)
        diagnostics_layout.addLayout(marker_form)
        layout.addWidget(self.diagnostics_group)

        self.lcd_group = QGroupBox("Experimental LCD Output")
        self.lcd_group.setProperty("section", "geometry")
        lcd_layout = QFormLayout(self.lcd_group)
        lcd_layout.setSpacing(6)
        self._configure_form(lcd_layout)
        self.check_lcd_output = QCheckBox(
            "Enable blocker on secondary display"
        )
        self.check_lcd_output.setToolTip(
            "Experimental stationary-rig output only. Requires a second display."
        )
        self.spin_lcd_radius = self._make_spin(2.0, 500.0, 40.0, " px")
        self.spin_lcd_radius.setDecimals(0)
        self.lcd_status = QLabel(
            "Disabled. White is the fail-safe output for a stripped TN panel."
        )
        self.lcd_status.setObjectName("mutedText")
        self.lcd_status.setWordWrap(True)
        lcd_layout.addRow(self.check_lcd_output)
        lcd_layout.addRow("Spot radius:", self.spin_lcd_radius)
        lcd_layout.addRow(self.lcd_status)
        layout.addWidget(self.lcd_group)

        self.check_show_advanced_configuration.toggled.connect(
            self._update_configuration_visibility)
        self._rebuild_configuration_flow(layout)
        layout.addStretch()
        self._update_detection_control_states()
        self._update_detection_advanced_visibility()
        self._refresh_detection_summary()
        self._drowsiness_controls_changed()
        self._update_configuration_visibility()
        self._update_mode_controls()

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _configure_form(layout: QFormLayout):
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)

    @staticmethod
    def _make_spin(min_val, max_val, default, suffix=""):
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSuffix(suffix)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setMinimumHeight(30)
        return spin

    @staticmethod
    def _make_index_spin(default):
        return CameraSelector(default)

    def _set_form_row_visible(self, layout, widget, visible):
        widget.setVisible(visible)
        label = layout.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    @staticmethod
    def _section_heading(text):
        heading = QLabel(text.upper())
        heading.setObjectName("configurationSectionHeading")
        return heading

    def _rebuild_configuration_flow(self, layout):
        """Arrange the sidebar in the order used during a test session."""

        groups = (
            self.mode_group,
            self.auto_camera_group,
            self.calibration_group,
            self.driver_monitoring_group,
            self.dist_group,
            self.manual_driver_group,
            self.light_detection_group,
            self.vehicle_group,
            self.light_group,
            self.movement_group,
            self.ws_group,
            self.camera_group,
            self.diagnostics_group,
            self.lcd_group,
        )
        for group in groups:
            layout.removeWidget(group)

        flow = (
            ("1  Operation", (self.mode_group,)),
            ("2  Cameras and calibration", (
                self.auto_camera_group, self.calibration_group)),
            ("3  Driver monitoring", (
                self.driver_monitoring_group, self.dist_group,
                self.manual_driver_group)),
            ("4  Road-light detection", (
                self.light_detection_group, self.vehicle_group,
                self.light_group, self.movement_group)),
            ("5  System geometry", (self.ws_group, self.camera_group)),
            ("6  Research and output", (
                self.diagnostics_group, self.lcd_group)),
        )
        self.configuration_headings = []
        for title, section_groups in flow:
            heading = self._section_heading(title)
            self.configuration_headings.append(heading)
            layout.addWidget(heading)
            for group in section_groups:
                layout.addWidget(group)

    def _update_configuration_visibility(self):
        """Keep the normal workflow concise while retaining research tools."""

        advanced = self.check_show_advanced_configuration.isChecked()
        self.camera_group.setVisible(advanced)
        self.lcd_group.setVisible(advanced)

    def _drowsiness_controls_changed(self, *_):
        custom = self.combo_drowsiness_profile.currentText() == "Custom"
        form = self.driver_monitoring_group.layout()
        for widget in (
            self.spin_eye_openness,
            self.spin_blink_duration,
            self.spin_perclos_threshold,
            self.spin_perclos_window,
            self.spin_yawn_openness,
            self.spin_yawn_duration,
        ):
            self._set_form_row_visible(form, widget, custom)
        self._emit_drowsiness_settings()

    def _emit_drowsiness_settings(self, *_):
        settings = self.get_drowsiness_settings()
        if not settings.enabled:
            self.drowsiness_status.setText(
                "Off. Experimental research indicator; not a safety-certified alarm.")
        else:
            profile = self.combo_drowsiness_profile.currentText().lower()
            self.drowsiness_status.setText(
                f"Enabled with {profile} thresholds; waiting for driver face data.")
        self.drowsiness_settings_changed.emit(settings)

    def _update_mode_controls(self):
        policy = self.mode_policy()
        self.mode_description.setText(policy.description)
        self.manual_driver_group.setEnabled(policy.manual_driver)
        self.light_group.setEnabled(policy.manual_headlight)
        self.vehicle_group.setEnabled(policy.manual_headlight)
        self.light_group.setVisible(policy.manual_headlight)
        self.vehicle_group.setVisible(policy.manual_headlight)
        self.movement_group.setVisible(policy.manual_headlight)
        self.dist_group.setEnabled(policy.use_driver_camera)
        self.driver_monitoring_group.setEnabled(policy.use_driver_camera)
        self.auto_camera_group.setVisible(True)
        self.spin_driver_camera.setEnabled(True)
        self._update_auto_controls()
        self.spin_driver_camera.setEnabled(
            not self.check_lock_driver_camera.isChecked())
        self._update_configuration_visibility()

    def _update_auto_controls(self):
        policy = self.mode_policy()
        road = policy.use_road_camera
        stereo = self.combo_detection_setup.currentText() == "Stereo Cameras"
        form = self.auto_camera_group.layout()
        # The active research build is calibrated stereo. The legacy
        # single-camera path remains in code for regression/fallback use, but
        # its setup/depth controls no longer clutter the normal workflow.
        self._set_form_row_visible(form, self.combo_detection_setup, False)
        for widget in (self.spin_headlight_camera,):
            self._set_form_row_visible(form, widget, True)
            widget.setEnabled(True)
        for widget in (
            self.spin_single_depth,
            self.spin_camera_hfov,
        ):
            self._set_form_row_visible(form, widget, road and not stereo)
            widget.setEnabled(road and not stereo)
        self._set_form_row_visible(
            form, self.spin_headlight_camera_2, stereo)
        self.spin_headlight_camera_2.setEnabled(stereo)
        self.light_detection_group.setVisible(road)
        self.btn_stereo_calibration.setVisible(road and stereo)
        self.stereo_status.setVisible(road and stereo)

        single_camera = not stereo
        self.calibration_group.setVisible(
            (policy.use_driver_camera or road) and single_camera)
        self.btn_guided_calibration.setVisible(single_camera)
        self.auto_note.setText(
            "Single camera: the Headlight camera selection is used. In Driver "
            "Position Fixed mode, the Driver camera is not opened. Road distance "
            "uses the assumed depth unless a matching lamp profile is active."
            if road and single_camera else
            "Stereo uses two road cameras. Both feeds must view the same light and "
            "the rigid pair must be calibrated."
            if road else
            "Assignments are saved in the panel, but inactive camera roles are "
            "not opened in the selected mode."
        )

    def set_available_cameras(self, devices):
        """Populate each role dropdown from one shared discovery result."""

        for selector in (
            self.spin_driver_camera,
            self.spin_headlight_camera,
            self.spin_headlight_camera_2,
        ):
            selector.set_available_cameras(devices)
        self.spin_driver_camera.setEnabled(
            bool(devices) and not self.check_lock_driver_camera.isChecked())

    def set_camera_scan_status(self, text):
        self.camera_scan_status.setText(text)

    def is_auto_light(self):
        """Compatibility name: true when the road-camera source is active."""
        return self.mode_policy().use_road_camera

    def operating_mode(self):
        return OperatingMode(self.combo_operating_mode.currentText())

    def mode_policy(self):
        return policy_for(self.operating_mode())

    def is_stereo_detection(self):
        return self.combo_detection_setup.currentText() == "Stereo Cameras"

    def _update_detection_control_states(self):
        camera_controls = self.check_apply_camera_controls.isChecked()
        self.check_auto_exposure.setEnabled(camera_controls)
        self.spin_exposure.setEnabled(
            camera_controls and not self.check_auto_exposure.isChecked())
        for widget in (
            self.spin_camera_brightness,
            self.spin_camera_contrast,
            self.spin_camera_gain,
        ):
            widget.setEnabled(camera_controls)
        self.spin_background_difference.setEnabled(
            self.check_background_rejection.isChecked())
        self.spin_local_contrast_threshold.setEnabled(
            self.check_local_contrast.isChecked())
        if not camera_controls:
            self.camera_control_feedback.setText(
                "Camera controls OFF — exposure, brightness, contrast, and "
                "gain are not sent. Automatic exposure is restored.")
        elif self.check_auto_exposure.isChecked():
            self.camera_control_feedback.setText(
                "Camera controls ON — automatic exposure is requested. "
                "Manual exposure is disabled; camera readback appears here.")
        else:
            self.camera_control_feedback.setText(
                "Camera controls ON — manual exposure and image controls are "
                "requested. Camera readback appears here.")

        self._refresh_detection_summary()

    def _update_detection_advanced_visibility(self):
        """Keep normal calibrated-stereo operation compact and focused."""

        visible = self.check_show_advanced_detection.isChecked()
        form = self.light_detection_group.layout()
        for widget in (
            self.check_apply_camera_controls,
            self.check_auto_exposure,
            self.spin_exposure,
            self.spin_camera_brightness,
            self.spin_camera_contrast,
            self.spin_camera_gain,
            self.camera_control_feedback,
            self.check_background_rejection,
            self.spin_background_difference,
            self.btn_capture_background,
            self.btn_clear_background,
            self.background_status,
            self.check_local_contrast,
            self.spin_local_contrast_threshold,
            self.spin_min_source_confidence,
            self.check_adaptive_threshold,
            self.spin_brightness_threshold,
            self.spin_min_light_area,
            self.spin_max_light_area,
            self.combo_blur_size,
            self.spin_morphology_iterations,
            self.spin_max_light_sources,
            self.spin_light_match_distance,
            self.btn_daylight_phone_preset,
            self.btn_reset_light_detection,
            self.detection_note,
        ):
            self._set_form_row_visible(form, widget, visible)

    def _refresh_detection_summary(self):
        if not hasattr(self, "detection_summary"):
            return
        settings = self.get_light_detection_settings()
        self.detection_summary.setText(
            f"Active: confidence {settings.minimum_confidence:.0%}, "
            f"area {settings.min_area_px:.0f}-{settings.max_area_px:.0f} px, "
            f"blur {settings.blur_size}x{settings.blur_size}, cleanup "
            f"{settings.morphology_iterations}, up to {settings.max_sources} "
            "sources. New stereo tracks are confirmed across frames.")

    def _minimum_light_area_changed(self, value):
        if value > self.spin_max_light_area.value():
            self.spin_max_light_area.setValue(value)

    def _maximum_light_area_changed(self, value):
        if value < self.spin_min_light_area.value():
            self.spin_min_light_area.setValue(value)

    def set_camera_control_feedback(self, text):
        self.camera_control_feedback.setText(text)

    def set_background_status(self, text):
        self.background_status.setText(text)

    def reset_light_detection_defaults(self):
        defaults = LightDetectionSettings()
        self.check_apply_camera_controls.setChecked(
            defaults.apply_camera_controls)
        self.check_auto_exposure.setChecked(defaults.auto_exposure)
        self.spin_exposure.setValue(defaults.exposure)
        self.spin_camera_brightness.setValue(defaults.brightness)
        self.spin_camera_contrast.setValue(defaults.contrast)
        self.spin_camera_gain.setValue(defaults.gain)
        self.check_background_rejection.setChecked(
            defaults.background_rejection)
        self.spin_background_difference.setValue(
            defaults.background_difference_threshold)
        self.check_local_contrast.setChecked(
            defaults.require_local_contrast)
        self.spin_local_contrast_threshold.setValue(
            defaults.local_contrast_threshold)
        self.spin_min_source_confidence.setValue(
            defaults.minimum_confidence * 100.0)
        self.check_adaptive_threshold.setChecked(defaults.adaptive_threshold)
        self.spin_brightness_threshold.setValue(defaults.brightness_threshold)
        self.spin_min_light_area.setValue(defaults.min_area_px)
        self.spin_max_light_area.setValue(defaults.max_area_px)
        self.combo_blur_size.setCurrentText(f"{defaults.blur_size} x {defaults.blur_size}")
        self.spin_morphology_iterations.setValue(
            defaults.morphology_iterations)
        self.spin_max_light_sources.setValue(defaults.max_sources)
        self.spin_light_match_distance.setValue(defaults.match_distance_px)
        self._update_detection_control_states()

    def load_daylight_phone_preset(self):
        """Load a repeatable starting point for a lamp near a bright window."""

        self.check_apply_camera_controls.setChecked(False)
        # Never let a stale or accidentally lamp-containing reference frame
        # silently veto the automatic detector when loading this preset.
        self.check_background_rejection.setChecked(False)
        self.check_adaptive_threshold.setChecked(True)
        self.spin_brightness_threshold.setValue(200)
        self.check_local_contrast.setChecked(True)
        self.spin_local_contrast_threshold.setValue(8)
        self.spin_background_difference.setValue(20)
        self.spin_min_light_area.setValue(5)
        self.spin_max_light_area.setValue(50000)
        self.spin_min_source_confidence.setValue(25)
        self.combo_blur_size.setCurrentText("3 x 3")
        self.spin_morphology_iterations.setValue(1)
        self.spin_max_light_sources.setValue(4)
        self.spin_light_match_distance.setValue(80)
        self._update_detection_control_states()

    def load_stable_stereo_preset(self):
        """Load the exact smooth settings validated on the current camera rig."""

        self.check_apply_camera_controls.setChecked(False)
        self.check_background_rejection.setChecked(False)
        self.check_adaptive_threshold.setChecked(True)
        self.spin_brightness_threshold.setValue(200)
        self.check_local_contrast.setChecked(True)
        self.spin_local_contrast_threshold.setValue(4)
        self.spin_min_source_confidence.setValue(32)
        self.spin_min_light_area.setValue(656)
        self.spin_max_light_area.setValue(50000)
        self.combo_blur_size.setCurrentText("9 x 9")
        self.spin_morphology_iterations.setValue(5)
        self.spin_max_light_sources.setValue(8)
        self.spin_light_match_distance.setValue(221)
        self._update_detection_control_states()

    def load_balanced_stereo_preset(self):
        """Favor shared-FOV coverage while temporal tracking removes flicker."""

        self.check_apply_camera_controls.setChecked(False)
        self.check_background_rejection.setChecked(False)
        self.check_adaptive_threshold.setChecked(True)
        self.spin_brightness_threshold.setValue(200)
        self.check_local_contrast.setChecked(True)
        self.spin_local_contrast_threshold.setValue(4)
        self.spin_min_source_confidence.setValue(30)
        self.spin_min_light_area.setValue(60)
        self.spin_max_light_area.setValue(50000)
        self.combo_blur_size.setCurrentText("5 x 5")
        self.spin_morphology_iterations.setValue(2)
        self.spin_max_light_sources.setValue(4)
        self.spin_light_match_distance.setValue(110)
        self._update_detection_control_states()

    def get_light_detection_settings(self):
        blur_text = self.combo_blur_size.currentText()
        blur_size = 1 if blur_text == "None" else int(blur_text.split()[0])
        return LightDetectionSettings(
            brightness_threshold=self.spin_brightness_threshold.value(),
            adaptive_threshold=self.check_adaptive_threshold.isChecked(),
            min_area_px=self.spin_min_light_area.value(),
            max_area_px=self.spin_max_light_area.value(),
            blur_size=blur_size,
            morphology_iterations=self.spin_morphology_iterations.value(),
            max_sources=self.spin_max_light_sources.value(),
            match_distance_px=self.spin_light_match_distance.value(),
            require_local_contrast=self.check_local_contrast.isChecked(),
            local_contrast_threshold=(
                self.spin_local_contrast_threshold.value()),
            minimum_confidence=(
                self.spin_min_source_confidence.value() / 100.0),
            background_rejection=(
                self.check_background_rejection.isChecked()),
            background_difference_threshold=(
                self.spin_background_difference.value()),
            apply_camera_controls=self.check_apply_camera_controls.isChecked(),
            auto_exposure=self.check_auto_exposure.isChecked(),
            exposure=self.spin_exposure.value(),
            brightness=self.spin_camera_brightness.value(),
            contrast=self.spin_camera_contrast.value(),
            gain=self.spin_camera_gain.value(),
        ).normalized()

    def get_drowsiness_settings(self):
        """Return default or operator-defined experimental thresholds."""

        enabled = self.check_drowsiness.isChecked()
        if self.combo_drowsiness_profile.currentText() != "Custom":
            return DrowsinessSettings(enabled=enabled)
        return DrowsinessSettings(
            enabled=enabled,
            eye_openness_threshold=self.spin_eye_openness.value(),
            blink_duration_ms=self.spin_blink_duration.value(),
            perclos_threshold=self.spin_perclos_threshold.value() / 100.0,
            perclos_window_s=self.spin_perclos_window.value(),
            yawn_openness_threshold=self.spin_yawn_openness.value(),
            yawn_duration_ms=self.spin_yawn_duration.value(),
        ).normalized()

    # ── public getters ──────────────────────────────────────────────

    def get_light_pos(self):
        """Base light-source position ``(x, y, z)``."""
        return (self.spin_light_x.value(),
                self.spin_light_y.value(),
                self.spin_light_z.value())

    def get_light_positions(self):
        """All light positions based on vehicle category (1-4 sources)."""
        bx, by, bz = self.get_light_pos()
        category = self.combo_vehicle.currentText()
        if category == "Four-Wheeler/Car":
            offsets = [(-8.0, 0.0, 0.0), (8.0, 0.0, 0.0)]
        elif category == "Extreme Vehicle":
            offsets = [(-10.0, 0.0, -4.0), (10.0, 0.0, -4.0),
                       (-10.0, 0.0, 4.0), (10.0, 0.0, 4.0)]
        else:
            offsets = [(0.0, 0.0, 0.0)]
        return [(bx + dx, by + dy, bz + dz) for dx, dy, dz in offsets]

    def get_windshield_dims(self):
        """``(width_cm, height_cm)``."""
        return (self.spin_ws_w.value(), self.spin_ws_h.value())

    def get_eye_distance(self):
        return self.spin_eye_dist.value()

    def get_manual_eye_pos(self):
        """Fixed/manual driver position ``(x, y, z)`` in centimetres."""
        return (
            self.spin_driver_x.value(),
            self.spin_driver_y.value(),
            self.spin_driver_z.value(),
        )

    def get_camera_pos(self):
        """Camera position ``(x, y, z)``."""
        return (self.spin_camera_x.value(),
                self.spin_camera_y.value(),
                self.spin_camera_z.value())
