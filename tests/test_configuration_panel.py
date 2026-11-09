"""Off-screen checks for the structured operator configuration flow."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from glare_tracker.widgets.controls import ControlsPanel


@pytest.fixture
def panel():
    application = QApplication.instance() or QApplication([])
    widget = ControlsPanel()
    widget._test_application = application
    return widget


def test_configuration_panel_has_standard_workflow_order(panel):
    assert [heading.text() for heading in panel.configuration_headings] == [
        "1  OPERATION",
        "2  CAMERAS AND CALIBRATION",
        "3  DRIVER MONITORING",
        "4  ROAD-LIGHT DETECTION",
        "5  SYSTEM GEOMETRY",
        "6  RESEARCH AND OUTPUT",
    ]
    assert panel.camera_group.isHidden()
    assert panel.lcd_group.isHidden()


def test_drowsiness_defaults_off_and_custom_thresholds_are_explicit(panel):
    defaults = panel.get_drowsiness_settings()
    assert not defaults.enabled
    assert defaults.eye_openness_threshold == pytest.approx(0.21)
    assert panel.spin_eye_openness.isHidden()

    panel.check_drowsiness.setChecked(True)
    panel.combo_drowsiness_profile.setCurrentText("Custom")
    panel.spin_eye_openness.setValue(0.24)
    panel.spin_perclos_threshold.setValue(30)
    custom = panel.get_drowsiness_settings()

    assert custom.enabled
    assert custom.eye_openness_threshold == pytest.approx(0.24)
    assert custom.perclos_threshold == pytest.approx(0.30)
    assert not panel.spin_eye_openness.isHidden()
