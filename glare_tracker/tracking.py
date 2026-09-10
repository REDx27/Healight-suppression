"""Tracking controller — all business logic extracted from MainWindow.

Owns calibration state, intersection calculation, light-movement
simulation, and FPS counting.  Receives raw eye data and updates all
panels accordingly.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

from glare_tracker.geometry import compute_intersection

if TYPE_CHECKING:
    from glare_tracker.widgets import (
        Scene3DWidget, Windshield2DWidget, ReadoutPanel, ControlsPanel,
    )


class TrackingController:
    """Central coordinator between the camera thread and the UI panels.

    Parameters
    ----------
    scene_3d : Scene3DWidget
    windshield_2d : Windshield2DWidget
    readout : ReadoutPanel
    controls : ControlsPanel
    """

    def __init__(
        self,
        scene_3d: Scene3DWidget,
        windshield_2d: Windshield2DWidget,
        readout: ReadoutPanel,
        controls: ControlsPanel,
    ):
        self._scene_3d = scene_3d
        self._windshield_2d = windshield_2d
        self._readout = readout
        self._controls = controls

        # State
        self._last_eye_cm: tuple[float, float, float] | None = None
        self._last_observed_eye_cm: tuple[float, float, float] | None = None
        self._calibration_offset = (0.0, 0.0, 0.0)
        self._baseline_captured = False
        self._frame_times: list[float] = []

        # Light movement simulation
        self._simulation_lights: list[tuple[float, float, float]] | None = None
        self._movement_phase = 0.0

    # ── properties ──────────────────────────────────────────────────

    @property
    def last_eye_cm(self):
        return self._last_eye_cm

    @property
    def last_observed_eye_cm(self):
        return self._last_observed_eye_cm

    # ── eye tracking callbacks ──────────────────────────────────────

    def on_eye_detected(self, x: float, y: float, z: float):
        """Called by the camera thread when an iris is detected."""
        observed = (x, y, z)
        self._last_observed_eye_cm = observed

        if not self._baseline_captured:
            self._capture_baseline(observed)

        adjusted = (
            x - self._calibration_offset[0],
            y - self._calibration_offset[1],
            z - self._calibration_offset[2],
        )
        self._last_eye_cm = adjusted
        self._frame_times.append(time.time())
        self.process_tracking(adjusted)

    def on_eye_lost(self):
        """Called by the camera thread when no face is detected."""
        self._last_eye_cm = None
        self._scene_3d.hide_tracking()
        self._windshield_2d.clear_glare()
        self._readout.set_value("eye_pos", "— (no face detected)", "#f44336")
        self._readout.set_intersections([])
        self._readout.set_value("status", "NO FACE ●", "#f44336")

    # ── core tracking calculation ───────────────────────────────────

    def process_tracking(self, eye_cm: tuple[float, float, float]):
        """Compute intersections and update all panels."""
        lights = self._simulation_lights or self._controls.get_light_positions()
        ws_w, ws_h = self._controls.get_windshield_dims()

        # Update 3D scene
        self._scene_3d.update_eye(*eye_cm)
        self._scene_3d.update_lights(lights)
        self._scene_3d.update_rays(eye_cm, lights)

        # Calculate intersections for each light source
        intersections = []
        valid_intersections = []
        glare_points = []
        hw = ws_w / 2

        for light in lights:
            intersection = compute_intersection(eye_cm, light)
            if intersection is None:
                intersections.append((None, False))
                continue
            ix, iy, iz = intersection
            in_bounds = (-hw <= ix <= hw) and (0.0 <= iz <= ws_h)
            intersections.append((intersection, in_bounds))
            glare_points.append(((ix + hw) / ws_w, (ws_h - iz) / ws_h, in_bounds))
            if in_bounds:
                valid_intersections.append(intersection)

        self._scene_3d.update_intersections(valid_intersections)

        # Update readout
        self._readout.set_value(
            "eye_pos",
            f"X:{eye_cm[0]:7.1f}  Y:{eye_cm[1]:7.1f}  Z:{eye_cm[2]:7.1f}",
            "#58a6ff",
        )
        self._readout.set_value("status", "TRACKING ●", "#4caf50")
        self._readout.set_intersections(intersections)

        # Update 2D windshield
        if glare_points:
            has_out = any(pt is not None and not ib for pt, ib in intersections)
            self._windshield_2d.update_glares(glare_points, has_out)
        else:
            self._windshield_2d.clear_glare()

    # ── calibration ─────────────────────────────────────────────────

    def calibrate(self):
        """Set the current observed eye position as the centre reference."""
        if self._last_observed_eye_cm:
            self._capture_baseline(self._last_observed_eye_cm)
            self._readout.set_value("status", "CALIBRATED ✓", "#4caf50")
        else:
            self._readout.set_value("status", "Calibration failed — no face", "#f44336")

    def _capture_baseline(self, observed):
        ws_h = self._controls.get_windshield_dims()[1]
        self._calibration_offset = (
            observed[0],
            0.0,
            observed[2] - ws_h / 2,
        )
        self._baseline_captured = True

    # ── parameter change handling ───────────────────────────────────

    def on_params_changed(self):
        """Called when any control spin-box or combo-box changes."""
        ws_w, ws_h = self._controls.get_windshield_dims()
        lights = self._controls.get_light_positions()

        self._scene_3d.update_windshield(ws_w, ws_h)
        self._scene_3d.update_lights(lights)
        self._scene_3d.update_camera(*self._controls.get_camera_pos())
        self._windshield_2d.set_windshield_aspect(ws_w, ws_h)

        self._readout.set_value(
            "light_pos",
            f"{len(lights)} source(s) — {self._controls.combo_vehicle.currentText()}",
        )

        if self._last_eye_cm:
            self.process_tracking(self._last_eye_cm)

    # ── light movement simulation ───────────────────────────────────

    def start_movement(self):
        """Begin the light-movement animation."""
        self._movement_phase = 0.0
        self._simulation_lights = self._compute_movement_positions()
        self.process_tracking(self._last_eye_cm or (0.0, -50.0, 9.75))

    def stop_movement(self):
        """Stop the animation and revert to static light positions."""
        self._simulation_lights = None

    def advance_movement(self):
        """Advance the animation by one tick (called from a QTimer)."""
        self._movement_phase = (self._movement_phase + 0.0125) % 1.0
        self._simulation_lights = self._compute_movement_positions()
        self.process_tracking(self._last_eye_cm or (0.0, -50.0, 9.75))

    def _compute_movement_positions(self):
        phase = self._movement_phase
        mode = self._controls.combo_movement.currentText()
        base_lights = self._controls.get_light_positions()
        if not base_lights:
            return []

        # Centroid of the headlight cluster
        cx = sum(p[0] for p in base_lights) / len(base_lights)
        cy = sum(p[1] for p in base_lights) / len(base_lights)
        cz = sum(p[2] for p in base_lights) / len(base_lights)

        if mode == "Coming at the opposite side":
            vx = cx - 90.0 + 180.0 * phase
            vy, vz = cy, cz
        elif mode == "Long distance":
            vx = cx
            vy = cy + 700.0 - 580.0 * phase
            vz = cz
        else:  # "Coming straight"
            vx = cx + 4.0 * np.sin(phase * 2 * np.pi)
            vy = cy + 240.0 - 210.0 * phase
            vz = cz

        return [
            (vx + (lx - cx), vy + (ly - cy), vz + (lz - cz))
            for lx, ly, lz in base_lights
        ]

    # ── FPS counter ─────────────────────────────────────────────────

    def update_fps(self):
        """Called every ~1 second to refresh the FPS readout."""
        now = time.time()
        self._frame_times = [t for t in self._frame_times if now - t < 2.0]
        if len(self._frame_times) > 1:
            fps = len(self._frame_times) / 2.0
            color = "#4caf50" if fps > 20 else "#ff9800"
            self._readout.set_value("fps", f"{fps:.1f} FPS", color)
        else:
            self._readout.set_value("fps", "— FPS", "#666")

    # ── reset state ─────────────────────────────────────────────────

    def reset_on_stream_stop(self):
        """Clear tracking state when the camera stream is stopped."""
        self._last_eye_cm = None
        self._last_observed_eye_cm = None
