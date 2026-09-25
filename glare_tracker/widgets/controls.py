"""User-configurable controls panel (windshield, camera, light, vehicle)."""

from PyQt5.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QFormLayout, QLabel,
    QPushButton, QDoubleSpinBox, QComboBox, QSpinBox, QSizePolicy,
)

from glare_tracker.widgets.icons import ICON_SIZE, IconFactory


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

        # ── Windshield ──
        ws_group = QGroupBox("Windshield")
        ws_layout = QFormLayout(ws_group)
        ws_layout.setSpacing(6)
        self.spin_ws_w = self._make_spin(1.0, 500.0, 34.5, " cm")
        self.spin_ws_h = self._make_spin(1.0, 500.0, 19.5, " cm")
        ws_layout.addRow("Width:", self.spin_ws_w)
        ws_layout.addRow("Height:", self.spin_ws_h)
        layout.addWidget(ws_group)

        # ── Camera position ──
        camera_group = QGroupBox("Camera Position")
        camera_layout = QFormLayout(camera_group)
        camera_layout.setSpacing(6)
        self.spin_camera_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_y = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_z = self._make_spin(-1000, 1000, 19.5, " cm")
        camera_layout.addRow("X:", self.spin_camera_x)
        camera_layout.addRow("Y:", self.spin_camera_y)
        camera_layout.addRow("Z:", self.spin_camera_z)
        layout.addWidget(camera_group)

        # ── Driver distance ──
        dist_group = QGroupBox("Driver Distance")
        dist_layout = QFormLayout(dist_group)
        dist_layout.setSpacing(6)
        self.spin_eye_dist = self._make_spin(5.0, 500.0, 50.0, " cm")
        self.distance_note = QLabel("Manual / reference measurement")
        self.distance_note.setObjectName("mutedText")
        dist_layout.addRow("Distance:", self.spin_eye_dist)
        dist_layout.addRow(self.distance_note)
        layout.addWidget(dist_group)

        # ── Vehicle / light mode ──
        vehicle_group = QGroupBox("Vehicle Type")
        vehicle_layout = QFormLayout(vehicle_group)
        vehicle_layout.setSpacing(6)
        self.combo_vehicle = QComboBox()
        self.combo_vehicle.addItems(["Motorcycle", "Four-Wheeler/Car", "Extreme Vehicle"])
        vehicle_layout.addRow("Category:", self.combo_vehicle)
        layout.addWidget(vehicle_group)

        # ── Headlight source ──
        light_group = QGroupBox("Light Source")
        light_layout = QFormLayout(light_group)
        light_layout.setSpacing(6)
        self.combo_light_mode = QComboBox()
        self.combo_light_mode.addItems(["Manual", "Auto"])
        self.spin_light_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_light_y = self._make_spin(-1000, 1000, 120.0, " cm")
        self.spin_light_z = self._make_spin(-1000, 5000, 10.0, " cm")
        light_layout.addRow("Mode:", self.combo_light_mode)
        light_layout.addRow("X:", self.spin_light_x)
        light_layout.addRow("Y:", self.spin_light_y)
        light_layout.addRow("Z:", self.spin_light_z)
        layout.addWidget(light_group)

        # ── Camera setup (shown only in Auto mode) ──
        self.auto_camera_group = QGroupBox("Auto Camera Setup")
        auto_layout = QFormLayout(self.auto_camera_group)
        auto_layout.setSpacing(6)
        self.combo_detection_setup = QComboBox()
        self.combo_detection_setup.addItems(["Single Camera", "Stereo Cameras"])
        self.spin_driver_camera = self._make_index_spin(0)
        self.spin_headlight_camera = self._make_index_spin(1)
        self.spin_headlight_camera_2 = self._make_index_spin(2)
        self.spin_single_depth = self._make_spin(10.0, 5000.0, 120.0, " cm")
        self.spin_camera_hfov = self._make_spin(10.0, 170.0, 70.0, " deg")
        self.spin_brightness_threshold = QSpinBox()
        self.spin_brightness_threshold.setRange(0, 255)
        self.spin_brightness_threshold.setValue(240)
        self.spin_brightness_threshold.setMinimumHeight(30)
        self.auto_note = QLabel(
            "Single-camera depth is assumed. Cameras default to the "
            "windshield top-centre.")
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
        self.auto_camera_group.hide()
        layout.addWidget(self.auto_camera_group)

        self.combo_light_mode.currentTextChanged.connect(self._update_auto_controls)
        self.combo_detection_setup.currentTextChanged.connect(self._update_auto_controls)

        # ── Light movement ──
        movement_group = QGroupBox("Simulation")
        movement_layout = QVBoxLayout(movement_group)
        movement_layout.setSpacing(6)
        self.combo_movement = QComboBox()
        self.combo_movement.addItems([
            "Coming straight",
            "Coming at the opposite side",
            "Long distance",
        ])
        self.btn_play_movement = QPushButton("Play Light Movement")
        self.btn_play_movement.setIcon(IconFactory.icon("play"))
        self.btn_play_movement.setIconSize(ICON_SIZE)
        self.btn_play_movement.setCheckable(True)
        self.btn_play_movement.setMinimumHeight(34)
        movement_layout.addWidget(self.combo_movement)
        movement_layout.addWidget(self.btn_play_movement)
        layout.addWidget(movement_group)

        layout.addStretch()

    # ── helpers ──────────────────────────────────────────────────────

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

    def _update_auto_controls(self):
        auto = self.combo_light_mode.currentText() == "Auto"
        stereo = self.combo_detection_setup.currentText() == "Stereo Cameras"
        self.auto_camera_group.setVisible(auto)
        self.spin_headlight_camera_2.setVisible(stereo)
        label = self.auto_camera_group.layout().labelForField(self.spin_headlight_camera_2)
        if label is not None:
            label.setVisible(stereo)
        for widget in (self.spin_light_x, self.spin_light_y, self.spin_light_z):
            widget.setEnabled(not auto)

    def is_auto_light(self):
        return self.combo_light_mode.currentText() == "Auto"

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

    def get_camera_pos(self):
        """Camera position ``(x, y, z)``."""
        return (self.spin_camera_x.value(),
                self.spin_camera_y.value(),
                self.spin_camera_z.value())
