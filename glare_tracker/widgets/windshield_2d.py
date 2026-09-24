"""2D front-view windshield widget with glowing glare spots."""

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QBrush, QRadialGradient
from PyQt5.QtWidgets import QWidget


class Windshield2DWidget(QWidget):
    """Custom-painted 2D front view of the windshield.

    Shows one or more glowing dots where glare intersections land.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 180)

        # Each entry: (norm_x, norm_y, in_bounds)
        self._glares: list[tuple[float, float, bool]] = []
        self._has_out_of_range = False

        # Windshield aspect ratio (updated from controls)
        self._ws_aspect = 34.5 / 19.4

    # ── public API ──────────────────────────────────────────────────

    def set_windshield_aspect(self, w_cm: float, h_cm: float):
        """Update the windshield aspect ratio used for drawing."""
        if h_cm > 0:
            self._ws_aspect = w_cm / h_cm
        self.update()

    def update_glare(self, norm_x: float, norm_y: float, in_bounds: bool):
        """Convenience for a single glare point."""
        self.update_glares([(norm_x, norm_y, in_bounds)], not in_bounds)

    def update_glares(self, glares, has_out_of_range=False):
        """Update multiple glare positions as ``(norm_x, norm_y, in_bounds)``."""
        self._glares = list(glares)
        self._has_out_of_range = has_out_of_range
        self.update()

    def clear_glare(self):
        """Remove all glare indicators."""
        self._glares = []
        self._has_out_of_range = False
        self.update()

    # ── painting ────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Dark background
        p.fillRect(self.rect(), QColor("#0b1422"))

        # Compute windshield rectangle preserving aspect ratio
        margin = 18
        title_space = 24
        bottom_space = 22
        avail_w = max(1, self.width() - 2 * margin)
        avail_h = max(1, self.height() - 2 * margin - title_space - bottom_space)
        ws_w = min(avail_w, avail_h * self._ws_aspect)
        ws_h = ws_w / self._ws_aspect
        ws_x = (self.width() - ws_w) / 2
        ws_y = margin + title_space + (avail_h - ws_h) / 2

        self._draw_windshield_outline(p, ws_x, ws_y, ws_w, ws_h)
        self._draw_crosshairs(p, ws_x, ws_y, ws_w, ws_h)
        self._draw_labels(p, ws_x, ws_y, ws_w, ws_h, margin)
        self._draw_glare_spots(p, ws_x, ws_y, ws_w, ws_h)

        p.end()

    def _draw_windshield_outline(self, p, ws_x, ws_y, ws_w, ws_h):
        boundary_color = "#ff647c" if self._has_out_of_range else "#168fb5"
        p.setPen(QPen(QColor(boundary_color), 3 if self._has_out_of_range else 2))
        p.setBrush(QColor(20, 115, 145, 35))
        p.drawRoundedRect(int(ws_x), int(ws_y), int(ws_w), int(ws_h), 8, 8)

    def _draw_crosshairs(self, p, ws_x, ws_y, ws_w, ws_h):
        grid_pen = QPen(QColor(255, 255, 255, 30), 1, Qt.DashLine)
        p.setPen(grid_pen)
        cx = ws_x + ws_w / 2
        cy = ws_y + ws_h / 2
        p.drawLine(int(ws_x), int(cy), int(ws_x + ws_w), int(cy))
        p.drawLine(int(cx), int(ws_y), int(cx), int(ws_y + ws_h))

    def _draw_labels(self, p, ws_x, ws_y, ws_w, ws_h, margin):
        cx = ws_x + ws_w / 2
        cy = ws_y + ws_h / 2

        label_font = QFont("Segoe UI", 8)
        p.setFont(label_font)
        p.setPen(QColor("#666"))
        p.drawText(int(cx - 10), int(ws_y - 6), "TOP")
        p.drawText(int(cx - 18), int(ws_y + ws_h + 16), "BOTTOM")
        p.drawText(max(4, int(ws_x - 28)), int(cy + 4), "LEFT")
        p.drawText(min(self.width() - 40, int(ws_x + ws_w + 4)), int(cy + 4), "RIGHT")

        # Title
        p.setPen(QColor("#d9f4ff"))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(max(8, int(ws_x)), margin + 16, "Windshield — Front View")

    def _draw_glare_spots(self, p, ws_x, ws_y, ws_w, ws_h):
        for norm_x, norm_y, in_bounds in self._glares:
            spot_x = ws_x + norm_x * ws_w
            spot_y = ws_y + norm_y * ws_h
            center = QPointF(spot_x, spot_y)

            if in_bounds:
                self._draw_in_bounds_spot(p, center)
            else:
                self._draw_out_of_bounds_spot(p, center, ws_x, ws_y, ws_w, ws_h)

    @staticmethod
    def _draw_in_bounds_spot(p, center):
        radius = 28.0
        glow = QRadialGradient(center, radius)
        glow.setColorAt(0.0, QColor(255, 235, 59, 220))
        glow.setColorAt(0.4, QColor(255, 152, 0, 130))
        glow.setColorAt(1.0, QColor(255, 87, 34, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(center, radius, radius)

        # Core dot
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(center, 4, 4)

    @staticmethod
    def _draw_out_of_bounds_spot(p, center, ws_x, ws_y, ws_w, ws_h):
        p.setPen(QPen(QColor(255, 80, 80, 180), 2, Qt.DashLine))
        p.setBrush(QColor(255, 80, 80, 60))
        p.drawEllipse(center, 12, 12)

        # Clamp indicator line to windshield edge
        p.setPen(QPen(QColor(255, 80, 80, 100), 1, Qt.DotLine))
        clamped_x = max(ws_x, min(ws_x + ws_w, center.x()))
        clamped_y = max(ws_y, min(ws_y + ws_h, center.y()))
        p.drawLine(int(clamped_x), int(clamped_y), int(center.x()), int(center.y()))
