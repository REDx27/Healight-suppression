"""Fail-safe secondary-display output for the prototype LCD panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import numpy as np

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPainter, QRadialGradient
from PyQt5.QtWidgets import QWidget

from glare_tracker.geometry import intersection_to_pixel


@dataclass(frozen=True)
class BlockerSpot:
    x_px: int
    y_px: int
    radius_px: float
    opacity: float = 1.0


class LCDBlockerWindow(QWidget):
    """Clear-state canvas with optional feathered blocker spots.

    The window is inert until explicitly enabled on a display. Clearing or
    disabling always removes blocker spots before hiding it. White is the
    default clear state because it normally gives maximum transmission through
    an unmodified LCD optical stack; an inverted mode is provided for bench
    verification of the actual panel.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GlareTracker Prototype Display Output")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self._enabled_output = False
        self._spots: tuple[BlockerSpot, ...] = ()
        self._panel_width_cm = 44.28
        self._panel_height_cm = 24.91
        self._resolution = (1920, 1080)
        self._radius_px = 40.0
        self._clear_state = "white"
        self._pixel_mapping = None
        self.tracking_authorized = True

    @property
    def output_enabled(self) -> bool:
        return self._enabled_output

    @property
    def spots(self) -> tuple[BlockerSpot, ...]:
        return self._spots

    @property
    def clear_state(self) -> str:
        return self._clear_state

    @property
    def resolution(self) -> tuple[int, int]:
        return self._resolution

    def set_clear_state(self, clear_state: str):
        """Select the clear background and inverse blocker colour."""

        clear_state = str(clear_state).strip().lower()
        if clear_state not in {"white", "black"}:
            raise ValueError("LCD clear state must be 'white' or 'black'")
        if clear_state == self._clear_state:
            return
        self._clear_state = clear_state
        self._spots = ()
        self.update()

    def configure_panel(
        self,
        width_cm: float,
        height_cm: float,
        resolution: tuple[int, int],
        radius_px: float,
    ):
        width_px, height_px = (int(resolution[0]), int(resolution[1]))
        if not np.isfinite([width_cm, height_cm]).all() or width_cm <= 0 or height_cm <= 0:
            raise ValueError("LCD physical dimensions must be positive")
        if width_px <= 0 or height_px <= 0:
            raise ValueError("LCD resolution must be positive")
        if not np.isfinite(radius_px) or radius_px <= 0:
            raise ValueError("Blocker radius must be positive")
        geometry_changed = (
            (float(width_cm), float(height_cm), (width_px, height_px))
            != (self._panel_width_cm, self._panel_height_cm, self._resolution))
        radius_changed = float(radius_px) != self._radius_px
        self._panel_width_cm = float(width_cm)
        self._panel_height_cm = float(height_cm)
        self._resolution = (width_px, height_px)
        self._radius_px = float(radius_px)
        if geometry_changed:
            # Existing pixel coordinates belong to the previous panel geometry.
            self.clear_output()
        elif radius_changed and self._spots:
            self._set_spots(tuple(BlockerSpot(s.x_px, s.y_px, self._radius_px, s.opacity)
                                  for s in self._spots))

    def enable_on_screen(self, screen):
        if screen is None:
            raise ValueError("A valid secondary screen is required")
        geometry = screen.geometry()
        self.configure_panel(
            self._panel_width_cm,
            self._panel_height_cm,
            (geometry.width(), geometry.height()),
            self._radius_px,
        )
        # Assign the native window to the requested QScreen before entering
        # fullscreen. Merely applying the screen geometry is unreliable on
        # multi-monitor Windows systems when the main window retains focus.
        self.winId()
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        self.setGeometry(geometry)
        self._enabled_output = True
        self.showFullScreen()
        self.raise_()
        self.update()

    def enable_for_testing(self):
        """Activate rendering logic without invoking platform fullscreen APIs."""

        self._enabled_output = True
        self.update()

    def update_intersections(self, intersections_cm: Iterable[tuple[float, float, float]]):
        if not self.tracking_authorized:
            self.clear_output()
            return
        if not self._enabled_output:
            return
        width_px, height_px = self._resolution
        spots = []
        for intersection in intersections_cm:
            pixel = intersection_to_pixel(
                tuple(intersection),
                self._panel_width_cm,
                self._panel_height_cm,
                width_px,
                height_px,
            )
            if pixel is not None:
                if self._pixel_mapping is not None:
                    u, v = self._pixel_mapping @ [intersection[0], intersection[2], 1.]
                    if not (0 <= u <= 1 and 0 <= v <= 1):
                        continue
                    pixel = (min(int(u * width_px), width_px - 1), min(int(v * height_px), height_px - 1))
                spots.append(
                    BlockerSpot(pixel[0], pixel[1], self._radius_px, 1.0)
                )
        self._set_spots(tuple(spots))

    def set_pixel_mapping(self, mapping):
        matrix = None if mapping is None else np.asarray(mapping, float)
        if matrix is not None and (matrix.shape != (2, 3) or not np.isfinite(matrix).all()):
            raise ValueError("LCD mapping must be a finite 2 x 3 matrix")
        if ((matrix is None and self._pixel_mapping is None)
                or (matrix is not None and self._pixel_mapping is not None
                    and np.array_equal(matrix, self._pixel_mapping))):
            return
        self._pixel_mapping = None if matrix is None else matrix.copy()
        self.clear_output()

    def show_alignment_mark(self, uv):
        if not self._enabled_output:
            return
        width, height = self._resolution
        self._spots = (BlockerSpot(int(uv[0] * width), int(uv[1] * height), 7., 1.),)
        self.update()

    def clear_output(self):
        self._set_spots(())

    def _set_spots(self, spots):
        if spots == self._spots:
            return
        self._spots = spots
        self.update()

    def show_test_pattern(self, pattern: str):
        """Show a deterministic alignment pattern without tracking input."""

        if not self._enabled_output:
            return
        pattern = str(pattern).strip().lower()
        if pattern in {"clear", "safe", "safe fill"}:
            self.clear_output()
            return
        width, height = self._resolution
        radius = self._radius_px
        if pattern in {"center", "center spot"}:
            points = ((width // 2, height // 2),)
        elif pattern in {"corners", "corners + center", "five point"}:
            inset = max(int(radius) + 4, min(width, height) // 20)
            points = (
                (inset, inset),
                (width - 1 - inset, inset),
                (width // 2, height // 2),
                (inset, height - 1 - inset),
                (width - 1 - inset, height - 1 - inset),
            )
        else:
            raise ValueError(f"Unknown LCD test pattern: {pattern}")
        self._spots = tuple(
            BlockerSpot(int(x), int(y), radius, 1.0) for x, y in points
        )
        self.update()

    def disable_output(self):
        self.clear_output()
        self._enabled_output = False
        self.repaint()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        inverted = self._clear_state == "black"
        background = QColor(0, 0, 0) if inverted else QColor(255, 255, 255)
        blocker_rgb = 255 if inverted else 0
        painter.fillRect(self.rect(), background)
        if not self._enabled_output:
            return
        for spot in self._spots:
            gradient = QRadialGradient(
                QPointF(float(spot.x_px), float(spot.y_px)), spot.radius_px
            )
            alpha = int(max(0.0, min(1.0, spot.opacity)) * 255)
            gradient.setColorAt(
                0.0, QColor(blocker_rgb, blocker_rgb, blocker_rgb, alpha))
            gradient.setColorAt(
                0.65, QColor(blocker_rgb, blocker_rgb, blocker_rgb, alpha))
            gradient.setColorAt(
                1.0, QColor(blocker_rgb, blocker_rgb, blocker_rgb, 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            diameter = 2.0 * spot.radius_px
            painter.drawEllipse(
                QPointF(float(spot.x_px), float(spot.y_px)),
                diameter / 2.0,
                diameter / 2.0,
            )

    def closeEvent(self, event):
        self.disable_output()
        event.accept()
