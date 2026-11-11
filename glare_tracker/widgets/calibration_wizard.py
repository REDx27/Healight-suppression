"""Guided single-camera demonstration calibration workflow."""

from __future__ import annotations

from collections import deque
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDoubleSpinBox, QFormLayout, QLabel, QPushButton,
    QVBoxLayout, QWizard, QWizardPage,
)

from glare_tracker.calibration import (
    DriverDepthCalibration,
    MonocularRangeCalibration,
    save_driver_depth_calibration,
    save_monocular_range_calibration,
    save_single_calibration,
)
from glare_tracker.widgets.toggle import ToggleSwitch


def _instruction(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.RichText)
    return label


def _distance_spin(default: float, minimum: float, maximum: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(1)
    spin.setSingleStep(1.0)
    spin.setValue(default)
    spin.setSuffix(" cm")
    return spin


class _RequiredCalibrationPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._complete = False

    def isComplete(self):
        return self._complete

    def set_complete(self, complete: bool):
        if self._complete != complete:
            self._complete = complete
            self.completeChanged.emit()


class DriverDepthPage(_RequiredCalibrationPage):
    """Collect a stable IPD observation at a measured reference distance."""

    def __init__(self, wizard):
        super().__init__(wizard)
        self.owner = wizard
        self.setTitle("1. Calibrate driver distance")
        self.setSubTitle("Estimate monocular eye depth from measured IPD.")

        layout = QVBoxLayout(self)
        layout.addWidget(_instruction(
            "<b>Before capture</b><ol>"
            "<li>Measure your interpupillary distance (IPD), centre-to-centre, "
            "with a millimetre ruler or an optician's value.</li>"
            "<li>Measure from the camera lens plane to the midpoint between your eyes.</li>"
            "<li>Sit normally, face the camera directly, keep your head level, and use even light.</li>"
            "<li>Hold still until at least 20 live samples are available, then capture.</li>"
            "</ol>"
            "This one-point procedure estimates focal scale; it does not measure lens "
            "distortion or camera-to-windshield pose."
        ))

        form = QFormLayout()
        self.ipd = _distance_spin(6.3, 4.0, 8.5)
        self.ipd.setSingleStep(0.1)
        self.reference_distance = _distance_spin(50.0, 20.0, 200.0)
        form.addRow("Measured IPD:", self.ipd)
        form.addRow("Lens-to-eye distance:", self.reference_distance)
        layout.addLayout(form)

        self.live = QLabel("Waiting for eye landmarks from driver camera...")
        self.live.setObjectName("mutedText")
        self.live.setWordWrap(True)
        layout.addWidget(self.live)

        self.capture = QPushButton("Capture Stable Driver Reference")
        self.capture.clicked.connect(self._capture)
        layout.addWidget(self.capture)

        self.result = QLabel("No driver reference captured yet.")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        layout.addStretch()

    def update_live(self, sample_count: int, separation_px: float):
        self.live.setText(
            f"Live iris separation: {separation_px:.1f} px · "
            f"stable samples available: {sample_count}")

    def _capture(self):
        samples = list(self.owner.eye_samples)
        if len(samples) < 20:
            self.result.setText(
                "<font color='#ffb74d'>Not enough samples. Face camera 0 and hold "
                "still until at least 20 samples are shown.</font>")
            return

        separations = np.asarray([sample[0] for sample in samples[-40:]])
        separation_px = float(np.median(separations))
        mad = float(np.median(np.abs(separations - separation_px)))
        variation = mad / max(1.0, separation_px)
        if separation_px < 8.0 or variation > 0.08:
            self.result.setText(
                "<font color='#ef5350'>Capture was unstable. Keep both eyes visible, "
                "face forward, improve lighting, and try again.</font>")
            return

        _, width, height = samples[-1]
        ipd_cm = self.ipd.value()
        distance_cm = self.reference_distance.value()
        focal_length_px = distance_cm * separation_px / ipd_cm
        calibration = DriverDepthCalibration(
            ipd_cm=ipd_cm,
            reference_distance_cm=distance_cm,
            reference_ipd_px=separation_px,
            focal_length_px=focal_length_px,
            image_size=(width, height),
            camera_index=self.owner.driver_camera_index,
        )
        save_driver_depth_calibration(calibration)
        save_single_calibration(calibration.as_intrinsic_calibration(), "driver_cam")
        self.owner.driver_calibration = calibration
        self.result.setText(
            "<font color='#66bb6a'><b>Driver reference saved.</b></font><br>"
            f"Median separation: {separation_px:.1f} px · focal scale: "
            f"{focal_length_px:.1f} px · variation: {variation * 100:.1f}%")
        self.set_complete(True)


class RoadRangePage(_RequiredCalibrationPage):
    """Collect apparent lamp diameter at one measured range."""

    def __init__(self, wizard):
        super().__init__(wizard)
        self.owner = wizard
        self.setTitle("2. Calibrate demonstration road-light range")
        self.setSubTitle("Estimate range from the apparent size of the same light.")

        layout = QVBoxLayout(self)
        layout.addWidget(_instruction(
            "<b>Reference setup</b><ol>"
            "<li>Use the same lamp or phone flashlight that will be used in the demo.</li>"
            "<li>Measure a straight line from the road-camera lens to the lamp face.</li>"
            "<li>Keep the lamp facing the camera and place it near the image centre.</li>"
            "<li>Make the room dim, avoid other bright reflections, and do not let the "
            "lamp wash out the whole frame.</li>"
            "<li>Hold it still until at least 20 diameter samples are available.</li>"
            "</ol>"
            "The resulting distance is an <b>apparent-size estimate</b>. It is valid only "
            "for the same lamp, camera settings, and similar viewing angle."
        ))

        form = QFormLayout()
        self.reference_distance = _distance_spin(200.0, 30.0, 2000.0)
        form.addRow("Measured lens-to-lamp distance:", self.reference_distance)
        layout.addLayout(form)

        self.live = QLabel("Waiting for an isolated bright light from road camera...")
        self.live.setObjectName("mutedText")
        self.live.setWordWrap(True)
        layout.addWidget(self.live)

        self.capture = QPushButton("Capture Stable Road-Light Reference")
        self.capture.clicked.connect(self._capture)
        layout.addWidget(self.capture)

        self.result = QLabel("No road-light reference captured yet.")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        layout.addStretch()

    def update_live(self, sample_count: int, diameter_px: float):
        self.live.setText(
            f"Live bright-core diameter: {diameter_px:.1f} px · "
            f"stable samples available: {sample_count}")

    def _capture(self):
        samples = list(self.owner.light_samples)
        if len(samples) < 20:
            self.result.setText(
                "<font color='#ffb74d'>Not enough samples. Keep one compact bright "
                "light visible and steady until at least 20 samples are shown.</font>")
            return

        diameters = np.asarray([sample[0] for sample in samples[-40:]])
        diameter_px = float(np.median(diameters))
        mad = float(np.median(np.abs(diameters - diameter_px)))
        variation = mad / max(1.0, diameter_px)
        if diameter_px < 3.0 or variation > 0.12:
            self.result.setText(
                "<font color='#ef5350'>Light size was unstable. Move the light farther "
                "from the camera if overexposed, remove reflections, and try again.</font>")
            return

        _, width, height = samples[-1]
        reference_cm = self.reference_distance.value()
        calibration = MonocularRangeCalibration(
            reference_distance_cm=reference_cm,
            reference_diameter_px=diameter_px,
            range_scale_cm_px=reference_cm * diameter_px,
            image_size=(width, height),
            camera_index=self.owner.road_camera_index,
            brightness_threshold=int(self.owner.road_thread.brightness_threshold),
        )
        save_monocular_range_calibration(calibration)
        self.owner.road_calibration = calibration
        self.result.setText(
            "<font color='#66bb6a'><b>Road reference saved.</b></font><br>"
            f"Median core diameter: {diameter_px:.1f} px · scale: "
            f"{calibration.range_scale_cm_px:.1f} cm·px · variation: "
            f"{variation * 100:.1f}%")
        self.set_complete(True)


class ReviewPage(QWizardPage):
    def __init__(self, wizard):
        super().__init__(wizard)
        self.owner = wizard
        self.setTitle("3. Review and activate")
        self.setSubTitle("Confirm how the demonstration estimates distance.")
        layout = QVBoxLayout(self)
        self.summary = _instruction("")
        layout.addWidget(self.summary)
        self.activate_driver = ToggleSwitch(
            "Use calibrated IPD-based driver depth")
        self.activate_driver.setChecked(True)
        self.activate_road = ToggleSwitch(
            "Use reference-size road-light range estimate")
        self.activate_road.setChecked(True)
        layout.addWidget(self.activate_driver)
        layout.addWidget(self.activate_road)
        layout.addWidget(_instruction(
            "<b>Accuracy notice:</b> These profiles improve a controlled classroom "
            "demonstration, but neither replaces camera-to-windshield extrinsic "
            "calibration. Road range remains especially sensitive to lamp bloom, "
            "exposure, lamp orientation, and use of a different light source."
        ))
        layout.addStretch()

    def initializePage(self):
        driver = self.owner.driver_calibration
        road = self.owner.road_calibration
        self.summary.setText(
            "<b>Driver profile</b><br>"
            f"IPD {driver.ipd_cm:.2f} cm at {driver.reference_distance_cm:.1f} cm; "
            f"focal scale {driver.focal_length_px:.1f} px.<br><br>"
            "<b>Road profile</b><br>"
            f"Light core {road.reference_diameter_px:.1f} px at "
            f"{road.reference_distance_cm:.1f} cm on camera "
            f"{road.camera_index} at threshold {road.brightness_threshold}.<br><br>"
            "After Finish, live values are labeled <b>EST</b>."
        )


class GuidedCalibrationWizard(QWizard):
    """Capture and save driver-depth and road-range demo profiles."""

    def __init__(
        self, driver_thread, road_thread, driver_camera_index: int,
        road_camera_index: int, parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Guided Single-Camera Calibration")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(760, 590)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)

        self.driver_thread = driver_thread
        self.road_thread = road_thread
        self.driver_camera_index = driver_camera_index
        self.road_camera_index = road_camera_index
        self.eye_samples = deque(maxlen=60)
        self.light_samples = deque(maxlen=60)
        self.driver_calibration = None
        self.road_calibration = None

        welcome = QWizardPage()
        welcome.setTitle("Guided demonstration calibration")
        welcome.setSubTitle("Read the measurement limits before continuing.")
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.addWidget(_instruction(
            "This wizard creates two controlled-demo profiles:<ul>"
            "<li><b>Driver depth:</b> inferred from apparent iris separation and your "
            "measured IPD.</li>"
            "<li><b>Road-light range:</b> inferred from the apparent diameter of one "
            "specific calibrated lamp.</li>"
            "</ul>"
            "You need a centimetre tape, steady camera mounts, even face lighting, "
            "a dim road-camera scene, and the same lamp used during the demo.<br><br>"
            "Do not use these estimates for driving decisions or claim them as true "
            "monocular ranging. Stereo, RGB-D, or another independent scale cue is "
            "required for general absolute distance."
        ))
        welcome_layout.addStretch()

        self.driver_page = DriverDepthPage(self)
        self.road_page = RoadRangePage(self)
        self.review_page = ReviewPage(self)
        self.addPage(welcome)
        self.addPage(self.driver_page)
        self.addPage(self.road_page)
        self.addPage(self.review_page)

        self.driver_thread.eye_pixels_detected.connect(self._on_eye_pixels)
        self.road_thread.light_observed.connect(self._on_light_observed)

    def _on_eye_pixels(self, lx, ly, rx, ry, width, height):
        separation = float(np.hypot(rx - lx, ry - ly))
        self.eye_samples.append((separation, int(width), int(height)))
        self.driver_page.update_live(len(self.eye_samples), separation)

    def _on_light_observed(self, u, v, diameter, width, height):
        self.light_samples.append((float(diameter), int(width), int(height)))
        self.road_page.update_live(len(self.light_samples), diameter)

    def done(self, result):
        try:
            self.driver_thread.eye_pixels_detected.disconnect(self._on_eye_pixels)
        except (TypeError, RuntimeError):
            pass
        try:
            self.road_thread.light_observed.disconnect(self._on_light_observed)
        except (TypeError, RuntimeError):
            pass
        super().done(result)

    @property
    def activate_driver_depth(self) -> bool:
        return self.review_page.activate_driver.isChecked()

    @property
    def activate_road_range(self) -> bool:
        return self.review_page.activate_road.isChecked()
