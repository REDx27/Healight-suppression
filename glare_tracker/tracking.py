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
from glare_tracker.light_sources import TrackedLightSource

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
        diagnostics=None,
        lcd_blocker=None,
    ):
        self._scene_3d = scene_3d
        self._windshield_2d = windshield_2d
        self._readout = readout
        self._controls = controls
        self._diagnostics = diagnostics
        self._lcd_blocker = lcd_blocker

        # State
        self._last_eye_cm: tuple[float, float, float] | None = None
        self._last_eyes_cm: tuple[
            tuple[float, float, float], tuple[float, float, float]
        ] | None = None
        self._last_observed_eye_cm: tuple[float, float, float] | None = None
        self._last_observed_eyes_cm: tuple[
            tuple[float, float, float], tuple[float, float, float]
        ] | None = None
        self._calibration_offset = (0.0, 0.0, 0.0)
        self._baseline_captured = False
        self._frame_times: list[float] = []
        self._live_light_sources: tuple[TrackedLightSource, ...] = ()
        self._rough_preview_sources: tuple[TrackedLightSource, ...] = ()

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

    @property
    def last_eyes_cm(self):
        """Last adjusted left/right eye coordinates, when both are available."""
        return self._last_eyes_cm

    # ── eye tracking callbacks ──────────────────────────────────────

    def on_eye_detected(self, x: float, y: float, z: float):
        """Compatibility path for a midpoint-only eye source."""
        observed = (x, y, z)
        self._last_observed_eye_cm = observed
        self._last_observed_eyes_cm = None

        if not self._baseline_captured:
            self._capture_baseline(observed)

        adjusted = (
            x - self._calibration_offset[0],
            y - self._calibration_offset[1],
            z - self._calibration_offset[2],
        )
        self._last_eye_cm = adjusted
        self._last_eyes_cm = None
        self._frame_times.append(time.time())
        self.process_tracking(adjusted)

    def on_eyes_detected(
        self,
        lx: float,
        ly: float,
        lz: float,
        rx: float,
        ry: float,
        rz: float,
    ):
        """Track both eyes and preserve their horizontal and vertical separation."""
        observed_eyes = ((lx, ly, lz), (rx, ry, rz))
        midpoint = self._midpoint(observed_eyes)
        self._last_observed_eyes_cm = observed_eyes
        self._last_observed_eye_cm = midpoint

        if not self._baseline_captured:
            self._capture_baseline(midpoint)

        adjusted_eyes = tuple(
            self._apply_calibration_offset(eye) for eye in observed_eyes
        )
        self._last_eyes_cm = adjusted_eyes
        self._last_eye_cm = self._midpoint(adjusted_eyes)
        self._frame_times.append(time.time())
        self.process_eye_tracking(adjusted_eyes)

    def on_eye_lost(self):
        """Called by the camera thread when no face is detected."""
        self._last_eye_cm = None
        self._last_eyes_cm = None
        if self._lcd_blocker is not None:
            self._lcd_blocker.clear_output()
        self._scene_3d.hide_tracking()
        self._windshield_2d.clear_glare()
        self._readout.set_value("eye_pos", "— (no face detected)", "#f44336")
        self._readout.set_intersections([])
        self._readout.set_value("status", "NO FACE ●", "#f44336")

    # ── core tracking calculation ───────────────────────────────────

    def on_lights_detected(
        self,
        sources: list[TrackedLightSource],
        calculate: bool = True,
    ):
        """Accept an arbitrary set of independently tracked bright sources."""

        self._rough_preview_sources = ()
        self._live_light_sources = tuple(sources)
        self.on_params_changed(calculate=calculate)

    def on_lights_lost(self):
        """Clear camera-owned lights so stale coordinates cannot remain active."""

        self._live_light_sources = ()
        self._rough_preview_sources = ()
        if self._lcd_blocker is not None:
            self._lcd_blocker.clear_output()
        if getattr(self._controls, "is_auto_light", lambda: False)():
            self._scene_3d.update_lights([])
            self._scene_3d.update_intersections([])
            self._windshield_2d.clear_glare()
            self._readout.set_intersections([])
            self._readout.set_value("light_pos", "-- no tracked sources")

    def preview_uncalibrated_lights(self, sources: list[TrackedLightSource]):
        """Render explicitly approximate intersections without LCD authority."""
        self._live_light_sources = ()
        self._rough_preview_sources = tuple(sources)
        if self._lcd_blocker is not None:
            self._lcd_blocker.clear_output()
        if self._controls.mode_policy().manual_driver:
            eyes = (self._controls.get_manual_eye_pos(),)
        elif self._last_eyes_cm:
            eyes = self._last_eyes_cm
        elif self._last_eye_cm:
            eyes = (self._last_eye_cm,)
        else:
            eyes = ()
        self._render_rough_intersections(eyes)

    def on_manual_eye(self, eye_cm: tuple[float, float, float]):
        """Apply a fixed/manual driver position to the geometry pipeline."""
        self._last_observed_eye_cm = eye_cm
        self._last_observed_eyes_cm = None
        self._last_eye_cm = eye_cm
        self._last_eyes_cm = None
        self.process_tracking(eye_cm)

    def process_tracking(self, eye_cm: tuple[float, float, float]):
        """Compute geometry for a midpoint/manual eye source."""
        self.process_eye_tracking((eye_cm,))

    def process_eye_tracking(self, eye_positions):
        """Compute one ray per eye and light without collapsing either eye."""
        eyes = tuple(tuple(eye) for eye in eye_positions[:2])
        if not eyes:
            return
        if self._rough_preview_sources and not self._live_light_sources:
            self._render_rough_intersections(eyes)
            return
        sources = self._active_light_sources()
        lights = [position for _, position, _, _ in sources]
        ws_w, ws_h = self._controls.get_windshield_dims()

        # Update 3D scene
        self._scene_3d.update_eyes(eyes)
        self._scene_3d.update_lights(lights)
        self._scene_3d.update_eye_rays(eyes, lights)

        # Calculate a distinct intersection for every light/eye pair. Keeping
        # the eye dimension here preserves head roll (vertical eye separation).
        intersections = []
        valid_intersections = []
        glare_points = []
        hw = ws_w / 2

        for light_index, (light_id, light, _, _) in enumerate(
                sources, start=1):
            for eye_index, eye_cm in enumerate(eyes, start=1):
                label = (
                    f"{light_id}/E{eye_index}"
                    if len(eyes) > 1 else light_id
                )
                intersection = compute_intersection(eye_cm, light)
                if intersection is None:
                    intersections.append((label, None, False))
                    continue
                ix, iy, iz = intersection
                in_bounds = (-hw <= ix <= hw) and (0.0 <= iz <= ws_h)
                intersections.append((label, intersection, in_bounds))
                glare_points.append(
                    ((ix + hw) / ws_w, (ws_h - iz) / ws_h, in_bounds)
                )
                if in_bounds:
                    valid_intersections.append(intersection)

        self._scene_3d.update_intersections(valid_intersections)
        if self._lcd_blocker is not None:
            self._lcd_blocker.update_intersections(valid_intersections)

        if (self._diagnostics is not None
                and self._diagnostics.is_active):
            light_timestamps = {
                source.stable_id: source.timestamp
                for source in self._live_light_sources
            }
            self._diagnostics.record_tracking(
                eyes,
                sources,
                intersections,
                light_timestamps=light_timestamps,
            )

        # Update readout
        if len(eyes) > 1:
            eye_text = "\n".join(
                f"E{idx} X:{eye[0]:.1f} Y:{eye[1]:.1f} Z:{eye[2]:.1f}"
                for idx, eye in enumerate(eyes, start=1)
            )
        else:
            eye = eyes[0]
            eye_text = f"X:{eye[0]:.1f}  Y:{eye[1]:.1f}  Z:{eye[2]:.1f}"
        self._readout.set_value("eye_pos", eye_text, "#60a5fa")
        self._readout.set_value("status", "TRACKING ●", "#4caf50")
        self._readout.set_intersections(intersections)

        # Update 2D windshield
        if glare_points:
            has_out = any(
                point is not None and not in_bounds
                for _, point, in_bounds in intersections
            )
            self._windshield_2d.update_glares(glare_points, has_out)
        else:
            self._windshield_2d.clear_glare()

    def _render_rough_intersections(self, eyes):
        """Render assumed-depth demo geometry, never research or physical output."""
        sources = self._rough_preview_sources
        positions = [source.position for source in sources]
        self._scene_3d.update_lights(positions)
        self._scene_3d.update_intersections([])
        if not sources or not eyes:
            self._windshield_2d.clear_glare()
            self._readout.set_intersections([])
            return

        eyes = tuple(tuple(eye) for eye in eyes[:2])
        ws_w, ws_h = self._controls.get_windshield_dims()
        half_width = ws_w / 2.0
        self._scene_3d.update_eyes(eyes)
        self._scene_3d.update_eye_rays(eyes, positions)
        intersections, visible, glare_points = [], [], []
        for source in sources:
            for eye_index, eye in enumerate(eyes, start=1):
                label = f"~{source.stable_id}/E{eye_index} ROUGH"
                point = compute_intersection(eye, source.position)
                if point is None:
                    intersections.append((label, None, False))
                    continue
                in_bounds = (
                    -half_width <= point[0] <= half_width
                    and 0.0 <= point[2] <= ws_h)
                intersections.append((label, point, in_bounds))
                glare_points.append((
                    (point[0] + half_width) / ws_w,
                    (ws_h - point[2]) / ws_h,
                    in_bounds,
                ))
                if in_bounds:
                    visible.append(point)
        self._scene_3d.update_intersections(visible)
        if glare_points:
            self._windshield_2d.update_glares(
                glare_points, any(not item[2] for item in glare_points))
        else:
            self._windshield_2d.clear_glare()
        source = sources[0]
        self._readout.set_value(
            "light_pos",
            f"ROUGH/UNCALIBRATED {source.stable_id}  "
            f"X:{source.position[0]:.1f}  assumed Y:{source.position[1]:.1f}  "
            f"Z:{source.position[2]:.1f}",
            "#f59e0b",
        )
        self._readout.set_value("status", "ROUGH DEMO - NOT CALIBRATED", "#f59e0b")
        self._readout.set_intersections(intersections)
        if self._lcd_blocker is not None:
            self._lcd_blocker.clear_output()

    # ── calibration ─────────────────────────────────────────────────

    def calibrate(self):
        """Set the current observed eye position as the centre reference."""
        if self._last_observed_eye_cm:
            self._capture_baseline(self._last_observed_eye_cm)
            if self._last_observed_eyes_cm:
                adjusted_eyes = tuple(
                    self._apply_calibration_offset(eye)
                    for eye in self._last_observed_eyes_cm
                )
                self._last_eyes_cm = adjusted_eyes
                self._last_eye_cm = self._midpoint(adjusted_eyes)
                self.process_eye_tracking(adjusted_eyes)
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

    def _apply_calibration_offset(self, eye):
        return tuple(
            coordinate - offset
            for coordinate, offset in zip(eye, self._calibration_offset)
        )

    @staticmethod
    def _midpoint(eyes):
        left, right = eyes
        return tuple((a + b) / 2.0 for a, b in zip(left, right))

    # ── parameter change handling ───────────────────────────────────

    def on_params_changed(self, calculate: bool = True):
        """Called when any control spin-box or combo-box changes."""
        ws_w, ws_h = self._controls.get_windshield_dims()
        sources = self._active_light_sources()
        lights = [position for _, position, _, _ in sources]

        self._scene_3d.update_windshield(ws_w, ws_h)
        self._scene_3d.update_lights(lights)
        self._scene_3d.update_camera(*self._controls.get_camera_pos())
        self._windshield_2d.set_windshield_aspect(ws_w, ws_h)

        if sources:
            light_id, (lx, ly, lz), confidence, state = sources[0]
            mode = "CAMERA" if self._controls.is_auto_light() else "FIXED"
            suffix = f" +{len(sources) - 1}" if len(sources) > 1 else ""
            quality = (
                f" {confidence:.0%} {state.replace('_', ' ')}"
                if confidence is not None else ""
            )
            self._readout.set_value(
                "light_pos",
                f"{mode}{suffix} {light_id}{quality}  "
                f"X:{lx:.1f}  Y:{ly:.1f}  Z:{lz:.1f}",
            )
        else:
            self._readout.set_value("light_pos", "— no sources")

        if not calculate:
            return
        if self._controls.mode_policy().manual_driver:
            self.on_manual_eye(self._controls.get_manual_eye_pos())
        elif self._last_eyes_cm:
            self.process_eye_tracking(self._last_eyes_cm)
        elif self._last_eye_cm:
            self.process_tracking(self._last_eye_cm)

    # ── light movement simulation ───────────────────────────────────

    def _active_light_sources(self):
        """Return IDs and positions without imposing a vehicle category."""

        if self._simulation_lights is not None:
            return [
                (f"L{index}", position, None, "simulated")
                for index, position in enumerate(
                    self._simulation_lights, start=1)
            ]
        if getattr(self._controls, "is_auto_light", lambda: False)():
            return [
                (
                    source.stable_id,
                    source.position,
                    source.confidence,
                    source.state,
                )
                for source in self._live_light_sources
            ]
        return [
            (f"L{index}", position, None, "fixed")
            for index, position in enumerate(
                self._controls.get_light_positions(), start=1)
        ]

    def start_movement(self):
        """Begin the light-movement animation."""
        self._movement_phase = 0.0
        self._simulation_lights = self._compute_movement_positions()
        self._process_current_eyes()

    def stop_movement(self):
        """Stop the animation and revert to static light positions."""
        self._simulation_lights = None

    def advance_movement(self):
        """Advance the animation by one tick (called from a QTimer)."""
        self._movement_phase = (self._movement_phase + 0.0125) % 1.0
        self._simulation_lights = self._compute_movement_positions()
        self._process_current_eyes()

    def _process_current_eyes(self):
        if self._last_eyes_cm:
            self.process_eye_tracking(self._last_eyes_cm)
        else:
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
        self._last_eyes_cm = None
        self._last_observed_eye_cm = None
        self._last_observed_eyes_cm = None
        self._live_light_sources = ()
        if self._lcd_blocker is not None:
            self._lcd_blocker.clear_output()
