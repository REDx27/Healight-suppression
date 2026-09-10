"""User-configurable controls panel (windshield, camera, light, vehicle)."""

from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QFormLayout, QLabel,
    QPushButton, QDoubleSpinBox, QComboBox,
)


class ControlsPanel(QGroupBox):
    """Sidebar panel with all user-configurable tracking parameters."""

    def __init__(self, parent=None):
        super().__init__("⚙ Controls", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Windshield ──
        ws_group = QGroupBox("Windshield (cm)")
        ws_layout = QFormLayout(ws_group)
        self.spin_ws_w = self._make_spin(1.0, 500.0, 34.5, " cm")
        self.spin_ws_h = self._make_spin(1.0, 500.0, 19.5, " cm")
        ws_layout.addRow("Width:", self.spin_ws_w)
        ws_layout.addRow("Height:", self.spin_ws_h)
        layout.addWidget(ws_group)

        # ── Camera position ──
        camera_group = QGroupBox("Camera Position (cm)")
        camera_layout = QFormLayout(camera_group)
        self.spin_camera_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_y = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_camera_z = self._make_spin(-1000, 1000, 30.0, " cm")
        camera_layout.addRow("X:", self.spin_camera_x)
        camera_layout.addRow("Y:", self.spin_camera_y)
        camera_layout.addRow("Z:", self.spin_camera_z)
        layout.addWidget(camera_group)

        # ── Driver distance ──
        dist_group = QGroupBox("Driver Distance (cm)")
        dist_layout = QFormLayout(dist_group)
        self.spin_eye_dist = self._make_spin(5.0, 500.0, 50.0, " cm")
        self.distance_note = QLabel("Manual/reference measurement")
        self.distance_note.setStyleSheet("color: #8b949e;")
        dist_layout.addRow("Distance:", self.spin_eye_dist)
        dist_layout.addRow(self.distance_note)
        layout.addWidget(dist_group)

        # ── Vehicle / light mode ──
        vehicle_group = QGroupBox("Vehicle / Light Mode")
        vehicle_layout = QFormLayout(vehicle_group)
        self.combo_vehicle = QComboBox()
        self.combo_vehicle.addItems(["Motorcycle", "Four-Wheeler/Car", "Extreme Vehicle"])
        vehicle_layout.addRow("Category:", self.combo_vehicle)
        layout.addWidget(vehicle_group)

        # ── Light source position ──
        light_group = QGroupBox("Light Source (cm)")
        light_layout = QFormLayout(light_group)
        self.spin_light_x = self._make_spin(-1000, 1000, 0.0, " cm")
        self.spin_light_y = self._make_spin(-1000, 1000, 120.0, " cm")
        self.spin_light_z = self._make_spin(-1000, 5000, 10.0, " cm")
        light_layout.addRow("X:", self.spin_light_x)
        light_layout.addRow("Y:", self.spin_light_y)
        light_layout.addRow("Z:", self.spin_light_z)
        layout.addWidget(light_group)

        # ── Light movement ──
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

        # ── Action buttons ──
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

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _make_spin(min_val, max_val, default, suffix=""):
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSuffix(suffix)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setMinimumHeight(28)
        return spin

    # ── public getters ──────────────────────────────────────────────

    def get_light_pos(self):
        """Base light-source position ``(x, y, z)``."""
        return (self.spin_light_x.value(),
                self.spin_light_y.value(),
                self.spin_light_z.value())

    def get_light_positions(self):
        """All light positions based on vehicle category (1–4 sources)."""
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
