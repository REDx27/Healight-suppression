"""Rendered-layout regressions for the compact desktop property editor."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QFormLayout, QScrollArea, QWidget

from glare_tracker.capture import CameraDevice
from glare_tracker.styles import DARK_STYLESHEET, CONTROL_HEIGHT
from glare_tracker.widgets.controls import ControlsPanel
from glare_tracker.widgets.dashboard import ApplicationHeader, SceneWorkspace
from glare_tracker.widgets.readout import ReadoutPanel
from glare_tracker.widgets.windshield_2d import Windshield2DWidget
from glare_tracker.widgets.property_panel import PropertyGroupBox
from glare_tracker.widgets.icons import IconFactory


@pytest.fixture
def editor():
    app = QApplication.instance() or QApplication([])
    panel = ControlsPanel()
    panel.setStyleSheet(DARK_STYLESHEET)
    for group in panel.findChildren(PropertyGroupBox):
        group.setExpanded(True)  # These tests deliberately inspect the editable content.
    panel.set_available_cameras([
        CameraDevice(0, 640, 480, "DirectShow", "Integrated Camera"),
        CameraDevice(1, 640, 480, "DirectShow", "USB Camera"),
        CameraDevice(2, 640, 480, "DirectShow", "USB Camera"),
    ])
    panel.resize(400, 760)
    panel.show()
    app.processEvents()
    yield panel, app
    panel.close()


@pytest.mark.parametrize("width", [360, 400, 480])
def test_camera_form_aligns_all_roles_and_fits_notes(editor, width):
    panel, app = editor
    panel.resize(width, 760)
    panel._select_property_context(1)
    app.processEvents()
    fields = (panel.spin_driver_camera, panel.spin_headlight_camera, panel.spin_headlight_camera_2)
    assert len({widget.x() for widget in fields}) == 1
    assert len({widget.width() for widget in fields}) == 1
    assert all(widget.height() == CONTROL_HEIGHT for widget in fields)
    assert panel.combo_operating_mode.fontMetrics().height() <= 17
    group = panel.auto_camera_group
    viewport = panel.property_pages.currentWidget().viewport()
    assert group.x() + group.width() <= viewport.width()
    assert panel.calibration_group.x() + panel.calibration_group.width() <= viewport.width()
    for note in (panel.camera_scan_status, panel.auto_note):
        assert note.height() >= note.heightForWidth(note.width())
        assert note.mapTo(group, QPoint(0, note.height())).y() <= group.height() - 8


def test_hidden_form_rows_leave_no_gaps_and_restore_custom_settings(editor):
    panel, app = editor
    panel._select_property_context(2)
    group = panel.driver_monitoring_group
    form = group.layout()
    app.processEvents()
    compact_height = group.height()
    # Custom fields are genuinely absent from layout geometry, not just painted
    # invisibly while their empty form rows keep consuming vertical spacing.
    assert form.getWidgetPosition(panel.spin_eye_openness)[0] == -1
    expected_order = (panel.spin_eye_openness, panel.spin_blink_duration,
                      panel.spin_perclos_threshold, panel.spin_perclos_window,
                      panel.spin_yawn_openness, panel.spin_yawn_duration)
    panel.check_drowsiness.setChecked(True)
    panel.combo_drowsiness_profile.setCurrentText("Custom")
    app.processEvents()
    assert group.height() > compact_height
    positions = [form.getWidgetPosition(widget)[0] for widget in expected_order]
    assert positions == sorted(positions) and min(positions) >= 0
    panel.spin_eye_openness.setValue(.27)
    panel.combo_drowsiness_profile.setCurrentText("Default")
    panel.check_drowsiness.setChecked(False)
    QTest.qWait(20)
    assert group.height() == compact_height
    panel.check_drowsiness.setChecked(True)
    panel.combo_drowsiness_profile.setCurrentText("Custom")
    assert panel.get_drowsiness_settings().eye_openness_threshold == pytest.approx(.27)


def test_long_calibration_status_expands_instead_of_clipping(editor):
    panel, app = editor
    panel.resize(360, 760)
    panel._select_property_context(1)
    status = panel.rig_calibration_status
    status.setText("Needs calibration / confirmation: " + "Measured camera mounts must be confirmed. " * 8)
    QTest.qWait(20)  # Let nested scroll/content layout requests propagate.
    group = panel.calibration_group
    assert status.height() >= status.heightForWidth(status.width())
    assert panel.check_rig_unchanged.y() >= status.y() + status.height()
    assert panel.check_rig_unchanged.y() + panel.check_rig_unchanged.height() <= group.height() - 8
    scroll = panel.property_pages.currentWidget()
    assert scroll.verticalScrollBar().maximum() > 0


def test_panel_preset_and_dimension_values_fit_without_wrapped_labels(editor):
    panel, app = editor
    panel.resize(360, 760)
    panel._select_property_context(4)
    app.processEvents()
    assert panel.panel_profile_editor.width() > panel.spin_ws_w.width()
    assert panel.spin_ws_w.height() == panel.spin_ws_h.height() == CONTROL_HEIGHT
    assert panel.spin_ws_w.x() == panel.spin_ws_h.x()
    assert panel.ws_group.layout().rowWrapPolicy() == QFormLayout.DontWrapRows


def test_camera_names_keep_full_device_information_on_hover(editor):
    panel, _ = editor
    selector = panel.spin_headlight_camera
    assert selector.currentText() == "1 · USB Camera"
    assert "640" in selector.toolTip() and "DirectShow" in selector.toolTip()
    assert selector.currentData() == 1


def test_toolbar_commands_remain_inside_small_windows():
    app = QApplication.instance() or QApplication([])
    header = ApplicationHeader("1.3.0")
    header.setStyleSheet(DARK_STYLESHEET)
    header.resize(960, 48)
    header.show()
    app.processEvents()
    for button in (header.btn_run, header.btn_standby, header.btn_stop,
                   header.btn_calibrate, header.btn_reset_view, header.panel_toggle):
        assert button.geometry().top() >= 0
        assert button.geometry().right() < header.width()
        assert button.geometry().bottom() < header.height()
    header.close()


def test_many_intersections_scroll_without_forcing_the_preview_strip_taller():
    app = QApplication.instance() or QApplication([])
    readout = ReadoutPanel()
    readout.setStyleSheet(DARK_STYLESHEET)
    readout.resize(300, 260)
    readout.show()
    readout.set_intersections([(f"L{i} / Eye {eye}", (float(i), 0., 12.), True)
                              for i in range(8) for eye in (1, 2)])
    app.processEvents()
    scroll = readout.findChild(QScrollArea)
    assert readout.height() == 260
    assert scroll.verticalScrollBar().maximum() > 0
    assert len([label for label in readout._intersection_labels if label.isVisible()]) == 16
    readout.close()


def test_windshield_inset_fits_short_workspace_and_leaves_legend_room():
    app = QApplication.instance() or QApplication([])
    inset = Windshield2DWidget()
    workspace = SceneWorkspace(QWidget(), inset)
    workspace.resize(960, 172)
    workspace.show()
    app.processEvents()
    assert inset.geometry().bottom() <= workspace.height() - 28
    assert inset.width() >= inset.minimumWidth()
    assert inset.height() >= inset.minimumHeight()
    workspace.close()


def test_settings_start_collapsed_and_restore_keyboard_and_mode_visibility():
    app = QApplication.instance() or QApplication([])
    panel = ControlsPanel()
    groups = panel.findChildren(PropertyGroupBox)
    assert groups and all(not group.isExpanded() for group in groups)
    assert all(group.maximumHeight() == group.HEADER_HEIGHT + 2 for group in groups)
    assert panel.combo_operating_mode.focusPolicy() == Qt.NoFocus
    hidden_before = panel.spin_eye_openness.isHidden()
    panel.show()
    app.processEvents()
    panel.mode_group.setFocus()
    QTest.keyClick(panel.mode_group, Qt.Key_Space)
    assert panel.mode_group.isExpanded()
    assert panel.combo_operating_mode.focusPolicy() != Qt.NoFocus
    panel.mode_group.setExpanded(False)
    assert panel.spin_eye_openness.isHidden() is hidden_before
    panel.close()
    app.processEvents()


def test_context_icons_are_semantic_bundled_assets_with_more_separation(editor):
    panel, _ = editor
    buttons = panel.property_context_buttons
    assert [button.property("contextIcon") for button in buttons] == [
        "operations", "camera", "user", "bulb", "monitor", "research"]
    rail = buttons[0].parentWidget()
    assert rail.layout().spacing() >= 12 and rail.width() >= 48
    for name in ("user", "bulb", "monitor", "research"):
        pixmap = IconFactory.pixmap(name, size=20)
        pixels = pixmap.toImage()
        assert any(pixels.pixelColor(x, y).alpha() > 0 for x in range(20) for y in range(20))
