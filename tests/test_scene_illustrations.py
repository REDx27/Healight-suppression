"""Schematic decoration never changes the measured positions or ray endpoints."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PyQt5.QtWidgets import QApplication
from glare_tracker.widgets.scene_3d import Scene3DWidget


def test_illustrations_follow_data_and_toggle_without_modifying_geometry():
    app = QApplication.instance() or QApplication([])
    scene = Scene3DWidget()
    eyes = ((-3., -50., 12.), (3., -50., 13.))
    lights = ((-10., 120., 15.), (10., 160., 18.))
    scene.update_eyes(eyes)
    scene.update_lights(lights)
    scene.update_eye_rays(eyes, lights)
    assert scene._driver_outline.visible()
    assert all(item.visible() for item in scene._lamp_outlines[:2])
    item_count = len(scene.gl_view.items)
    rays = tuple(np.array(line.pos, copy=True) for line in scene._ray_lines)
    scene.context_toggle.setChecked(False)
    assert not scene._driver_outline.visible()
    assert not any(item.visible() for item in scene._lamp_outlines)
    scene.context_toggle.setChecked(True)
    scene._toggle_scene_theme(True)
    assert scene._last_eye_positions == eyes and scene._last_light_positions == lights
    for original, line in zip(rays, scene._ray_lines):
        np.testing.assert_array_equal(original, line.pos)
    scene.light_toggle.click()
    assert not any(item.visible() for item in scene._lamp_outlines)
    scene.hide_tracking()
    assert not scene._driver_outline.visible()
    assert len(scene.gl_view.items) == item_count
    scene.close()


def test_stationary_lamp_buffers_and_hidden_models_do_not_update(monkeypatch):
    app = QApplication.instance() or QApplication([])
    scene = Scene3DWidget()
    lights = tuple((float(i * 10), 120., 15.) for i in range(8))
    scene.update_lights(lights)
    lamp_updates, head_updates = [], []
    for item in scene._lamp_outlines:
        original = item.setData
        def count_lamp(*args, target=original, **kwargs):
            lamp_updates.append(True)
            return target(*args, **kwargs)
        monkeypatch.setattr(item, "setData", count_lamp)
    original_head = scene._driver_outline.setData
    def count_head(*args, **kwargs):
        head_updates.append(True)
        return original_head(*args, **kwargs)
    monkeypatch.setattr(scene._driver_outline, "setData", count_head)
    for i in range(200):
        scene.update_eyes(((i / 100., -50., 12.),))
    assert len(head_updates) == 200 and len(lamp_updates) == 0
    scene.context_toggle.setChecked(False)
    scene.update_eyes(((10., -50., 12.),))
    moved = tuple((p[0], p[1] + 5., p[2]) for p in lights)
    scene.update_lights(moved)
    assert len(head_updates) == 200 and len(lamp_updates) == 0
    scene.context_toggle.setChecked(True)
    assert len(head_updates) == 201 and len(lamp_updates) == 8
    np.testing.assert_allclose(scene._lamp_outlines[0].pos, scene._lamp_shape + moved[0])
    scene._toggle_scene_theme(True)
    assert len(lamp_updates) == 16  # Theme changes still reach visible buffers.
    scene.close()
    app.processEvents()
