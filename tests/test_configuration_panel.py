"""Off-screen checks for the structured operator configuration flow."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QToolButton, QWidget

from glare_tracker.widgets.controls import ControlsPanel
from glare_tracker.widgets.toggle import ToggleSwitch
from glare_tracker.widgets.property_panel import PropertyGroupBox


@pytest.fixture
def panel():
    application = QApplication.instance() or QApplication([])
    widget = ControlsPanel()
    widget._test_application = application
    return widget


def test_configuration_panel_has_focused_property_contexts(panel):
    assert [title.text() for title in panel.property_page_titles] == [
        "OPERATION",
        "CAMERAS",
        "DRIVER",
        "ROAD LIGHTS",
        "GEOMETRY",
        "RESEARCH",
    ]
    assert len(panel.property_context_buttons) == 6
    assert panel.property_pages.currentIndex() == 0
    panel.property_context_buttons[2].click()
    assert panel.property_pages.currentIndex() == 2
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


def test_binary_settings_use_accessible_toggle_switches(panel):
    toggles = (
        panel.check_show_advanced_configuration,
        panel.check_lock_driver_camera,
        panel.check_drowsiness,
        panel.check_adaptive_threshold,
        panel.check_record_diagnostics,
        panel.check_lcd_output,
    )
    assert all(isinstance(toggle, ToggleSwitch) for toggle in toggles)
    assert panel.check_lock_driver_camera.isChecked()
    assert panel.check_lock_driver_camera.position == pytest.approx(1.0)
    before = panel.check_drowsiness.isChecked()
    panel.check_drowsiness.click()
    assert panel.check_drowsiness.isChecked() is not before


def test_advanced_toggle_has_visible_feedback_and_grouped_vectors(panel):
    assert "hidden" in panel.advanced_configuration_note.text().lower()
    assert panel.advanced_shortcuts.isHidden()
    panel.check_show_advanced_configuration.setChecked(True)
    assert not panel.camera_group.isHidden()
    assert not panel.lcd_group.isHidden()
    assert not panel.advanced_shortcuts.isHidden()
    assert "Geometry" in panel.advanced_configuration_note.text()
    assert "Research" in panel.advanced_configuration_note.text()
    panel.btn_open_advanced_geometry.click()
    assert panel.property_pages.currentIndex() == 4
    assert panel.property_context_buttons[4].isChecked()

    vector_editors = panel.findChildren(QWidget, "vectorEditor")
    assert len(vector_editors) == 4
    assert all(editor.layout().rowCount() == 3 for editor in vector_editors)


def test_property_sections_are_real_collapsible_panels(panel):
    section = panel.mode_group
    assert isinstance(section, PropertyGroupBox)
    assert section.title() == "Operating Mode"
    assert section.isExpanded()

    section.setExpanded(False)
    assert not section.isExpanded()
    assert section.maximumHeight() == section.HEADER_HEIGHT + 2
    # Collapsing clips the panel without corrupting the workflow visibility
    # state of its children.
    assert not panel.combo_operating_mode.isHidden()

    section.setExpanded(True)
    assert section.isExpanded()
    assert section.maximumHeight() == 16777215


def test_vector_axis_lock_and_reset_controls_are_functional(panel):
    locks = panel.camera_group.findChildren(QToolButton, "vectorLockButton")
    resets = panel.camera_group.findChildren(QToolButton, "vectorResetButton")
    assert len(locks) == 3
    assert len(resets) == 3

    locks[0].click()
    assert panel.spin_camera_x.isReadOnly()
    assert "Unlock" in locks[0].toolTip()
    locks[0].click()
    assert not panel.spin_camera_x.isReadOnly()

    panel.spin_camera_x.setValue(25.0)
    resets[0].click()
    assert panel.spin_camera_x.value() == pytest.approx(0.0)
