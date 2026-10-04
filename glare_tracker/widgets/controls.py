"""User-configurable controls panel (windshield, camera, light, vehicle)."""

from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QFormLayout, QLabel,
    QPushButton, QDoubleSpinBox, QComboBox, QSpinBox, QSizePolicy, QCheckBox,
)

from glare_tracker.widgets.icons import ICON_SIZE, IconFactory
from glare_tracker.operating_modes import OperatingMode, policy_for


class ControlsPanel(QWidget):
    """Sidebar panel with all user-configurable tracking parameters.

    Uses a flat QWidget (not nested QGroupBox) for cleaner rendering
    inside the OperationsSidebar tab.
    """

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
        mode_layout.addWidget(self.combo_operating_mode)
        mode_layout.addWidget(self.mode_description)
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

        # ── Camera setup (shown only in Auto mode) ──
        self.auto_camera_group = QGroupBox("Camera Setup")
        self.auto_camera_group.setProperty("section", "vision")
        auto_layout = QFormLayout(self.auto_camera_group)
        auto_layout.setSpacing(6)
        self._configure_form(auto_layout)
        self.combo_detection_setup = QComboBox()
        self.combo_detection_setup.addItems(["Single Camera", "Stereo Cameras"])
        self.spin_driver_camera = self._make_index_spin(0)
        self.spin_headlight_camera = self._make_index_spin(1)
        self.spin_headlight_camera_2 = self._make_index_spin(2)
        self.spin_single_depth = self._make_spin(10.0, 5000.0, 120.0, " cm")
        self.spin_camera_hfov = self._make_spin(10.0, 170.0, 70.0, " deg")
        self.spin_brightness_threshold = QSpinBox()
        self.spin_brightness_threshold.setRange(0, 255)
        self.spin_brightness_threshold.setValue(210)
        self.spin_brightness_threshold.setMinimumHeight(30)
        self.auto_note = QLabel()
        self.auto_note.setWordWrap(True)
        self.auto_note.setObjectName("mutedText")
        auto_layout.addRow("Setup:", self.combo_detection_setup)
        auto_layout.addRow("Driver camera:", self.spin_driver_camera)
        auto_layout.addRow("Headlight camera:", self.spin_headlight_camera)
        auto_layout.addRow("Stereo camera 2:", self.spin_headlight_camera_2)
        auto_layout.addRow("Assumed depth:", self.spin_single_depth)
        auto_layout.addRow("Camera HFOV:", self.spin_camera_hfov)
        auto_layout.addRow("Brightness threshold:", self.spin_brightness_threshold)
        auto_layout.addRow(self.auto_note)
        layout.addWidget(self.auto_camera_group)

        self.combo_operating_mode.currentTextChanged.connect(self._update_mode_controls)
        self.combo_detection_setup.currentTextChanged.connect(self._update_auto_controls)

        # ── Light movement ──
        movement_group = QGroupBox("Simulation")
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

        layout.addStretch()
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
        spin = QSpinBox()
        spin.setRange(0, 20)
        spin.setValue(default)
        spin.setMinimumHeight(30)
        return spin

    def _set_form_row_visible(self, layout, widget, visible):
        widget.setVisible(visible)
        label = layout.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _update_mode_controls(self):
        policy = self.mode_policy()
        self.mode_description.setText(policy.description)
        self.manual_driver_group.setEnabled(policy.manual_driver)
        self.light_group.setEnabled(policy.manual_headlight)
        self.dist_group.setEnabled(policy.use_driver_camera)
        self.auto_camera_group.setVisible(
            policy.use_driver_camera or policy.use_road_camera)
        self.spin_driver_camera.setEnabled(policy.use_driver_camera)
        self._update_auto_controls()

    def _update_auto_controls(self):
        policy = self.mode_policy()
        road = policy.use_road_camera
        stereo = self.combo_detection_setup.currentText() == "Stereo Cameras"
        form = self.auto_camera_group.layout()
        for widget in (
            self.combo_detection_setup,
            self.spin_headlight_camera,
            self.spin_single_depth,
            self.spin_camera_hfov,
            self.spin_brightness_threshold,
        ):
            self._set_form_row_visible(form, widget, road)
            widget.setEnabled(road)
        self._set_form_row_visible(
            form, self.spin_headlight_camera_2, road and stereo)
        self.spin_headlight_camera_2.setEnabled(road and stereo)

        single_camera = not stereo
        self.calibration_group.setVisible(
            (policy.use_driver_camera or road) and single_camera)
        self.btn_guided_calibration.setVisible(single_camera)
        self.auto_note.setText(
            "Single-camera road distance is estimated from a calibrated test lamp; "
            "without that profile it uses the assumed depth."
            if road and single_camera else
            "Stereo uses two road cameras. Both feeds must view the same light and "
            "the rigid pair must be calibrated."
            if road else
            "Only the driver-facing camera is required in this mode."
        )

    def is_auto_light(self):
        """Compatibility name: true when the road-camera source is active."""
        return self.mode_policy().use_road_camera

    def operating_mode(self):
        return OperatingMode(self.combo_operating_mode.currentText())

    def mode_policy(self):
        return policy_for(self.operating_mode())

    def is_stereo_detection(self):
        return self.combo_detection_setup.currentText() == "Stereo Cameras"

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
