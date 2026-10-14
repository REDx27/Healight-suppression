"""Experimental secondary-display output for a stripped transparent LCD panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

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
    """White safe-state canvas with optional feathered black blocker spots.

    The window is inert until explicitly enabled on a display. Clearing or
    disabling always returns it to an all-white output before hiding it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GlareTracker Experimental LCD Output")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self._enabled_output = False
        self._spots: tuple[BlockerSpot, ...] = ()
        self._panel_width_cm = 34.5
        self._panel_height_cm = 19.5
        self._resolution = (1920, 1080)
        self._radius_px = 40.0

    @property
    def output_enabled(self) -> bool:
        return self._enabled_output

    @property
    def spots(self) -> tuple[BlockerSpot, ...]:
        return self._spots

    def configure_panel(
        self,
        width_cm: float,
        height_cm: float,
        resolution: tuple[int, int],
        radius_px: float,
    ):
        width_px, height_px = (int(resolution[0]), int(resolution[1]))
        if width_cm <= 0 or height_cm <= 0:
            raise ValueError("LCD physical dimensions must be positive")
        if width_px <= 0 or height_px <= 0:
            raise ValueError("LCD resolution must be positive")
        if radius_px <= 0:
            raise ValueError("Blocker radius must be positive")
        self._panel_width_cm = float(width_cm)
        self._panel_height_cm = float(height_cm)
        self._resolution = (width_px, height_px)
        self._radius_px = float(radius_px)

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
                spots.append(
                    BlockerSpot(pixel[0], pixel[1], self._radius_px, 1.0)
                )
        self._spots = tuple(spots)
        self.update()

    def clear_output(self):
        self._spots = ()
        self.update()

    def disable_output(self):
        self.clear_output()
        self._enabled_output = False
        self.repaint()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        if not self._enabled_output:
            return
        for spot in self._spots:
            gradient = QRadialGradient(
                QPointF(float(spot.x_px), float(spot.y_px)), spot.radius_px
            )
            alpha = int(max(0.0, min(1.0, spot.opacity)) * 255)
            gradient.setColorAt(0.0, QColor(0, 0, 0, alpha))
            gradient.setColorAt(0.65, QColor(0, 0, 0, alpha))
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
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
