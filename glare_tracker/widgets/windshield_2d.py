"""2D front-view windshield widget with glowing glare spots."""

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QRadialGradient,
    QLinearGradient, QPixmap,
)
from PyQt5.QtWidgets import QWidget, QSizePolicy


class Windshield2DWidget(QWidget):
    """Custom-painted 2D front view of the windshield.

    Shows one or more glowing dots where glare intersections land.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Each entry: (norm_x, norm_y, in_bounds)
        self._glares: list[tuple[float, float, bool]] = []
        self._has_out_of_range = False

        # Windshield aspect ratio (updated from controls)
        self._ws_aspect = 34.5 / 19.4
        self._static_layer: QPixmap | None = None
        self._static_geometry = (0.0, 0.0, 1.0, 1.0)

    # ── public API ──────────────────────────────────────────────────

    def set_windshield_aspect(self, w_cm: float, h_cm: float):
        if h_cm > 0:
            aspect = w_cm / h_cm
            if abs(aspect - self._ws_aspect) > 1e-6:
                self._ws_aspect = aspect
                self._invalidate_static_layer()
                self.update()

    def update_glare(self, norm_x: float, norm_y: float, in_bounds: bool):
        self.update_glares([(norm_x, norm_y, in_bounds)], not in_bounds)

    def update_glares(self, glares, has_out_of_range=False):
        self._glares = list(glares)
        if self._has_out_of_range != has_out_of_range:
            self._static_layer = None
        self._has_out_of_range = has_out_of_range
        self.update()

    def clear_glare(self):
        self._glares = []
        if self._has_out_of_range:
            self._static_layer = None
        self._has_out_of_range = False
        self.update()

    # ── painting ────────────────────────────────────────────────────

    def paintEvent(self, event):
        if self._static_layer is None or self._static_layer.size() != self.size():
            self._build_static_layer()

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(0, 0, self._static_layer)
        self._draw_glare_spots(p, *self._static_geometry)
        p.end()

    def resizeEvent(self, event):
        self._static_layer = None
        super().resizeEvent(event)

    def _invalidate_static_layer(self):
        self._static_layer = None

    def _build_static_layer(self):
        """Cache gradients, labels, and grid lines that rarely change."""
        self._static_layer = QPixmap(self.size())
        self._static_layer.fill(Qt.transparent)
        p = QPainter(self._static_layer)
        p.setRenderHint(QPainter.Antialiasing)

        # Deep dark background with subtle gradient
        bg_grad = QLinearGradient(0, 0, 0, self.height())
        bg_grad.setColorAt(0.0, QColor("#080e16"))
        bg_grad.setColorAt(1.0, QColor("#060a10"))
        p.fillRect(self.rect(), QBrush(bg_grad))

        # Compute windshield rectangle preserving aspect ratio
        margin = 16
        title_space = 22
        bottom_space = 18
        avail_w = max(1, self.width() - 2 * margin)
        avail_h = max(1, self.height() - 2 * margin - title_space - bottom_space)
        ws_w = min(avail_w, avail_h * self._ws_aspect)
        ws_h = ws_w / self._ws_aspect
        ws_x = (self.width() - ws_w) / 2
        ws_y = margin + title_space + (avail_h - ws_h) / 2

        self._static_geometry = (ws_x, ws_y, ws_w, ws_h)
        self._draw_windshield_outline(p, ws_x, ws_y, ws_w, ws_h)
        self._draw_crosshairs(p, ws_x, ws_y, ws_w, ws_h)
        self._draw_labels(p, ws_x, ws_y, ws_w, ws_h, margin)
        p.end()

    def _draw_windshield_outline(self, p, ws_x, ws_y, ws_w, ws_h):
        is_alert = self._has_out_of_range

        # Outer glow
        glow_color = QColor("#f87171") if is_alert else QColor("#0e7490")
        glow_color.setAlpha(30)
        glow_pen = QPen(glow_color, 6)
        p.setPen(glow_pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(ws_x - 2, ws_y - 2, ws_w + 4, ws_h + 4), 9, 9)

        # Main border
        border_color = QColor("#f87171") if is_alert else QColor("#22b8cf")
        p.setPen(QPen(border_color, 2))

        # Fill gradient
        fill = QLinearGradient(ws_x, ws_y, ws_x, ws_y + ws_h)
        fill.setColorAt(0.0, QColor(14, 116, 144, 20))
        fill.setColorAt(1.0, QColor(14, 116, 144, 8))
        p.setBrush(QBrush(fill))

        p.drawRoundedRect(QRectF(ws_x, ws_y, ws_w, ws_h), 7, 7)

    def _draw_crosshairs(self, p, ws_x, ws_y, ws_w, ws_h):
        cx = ws_x + ws_w / 2
        cy = ws_y + ws_h / 2

        # Grid lines
        grid_pen = QPen(QColor(255, 255, 255, 18), 1, Qt.DashLine)
        p.setPen(grid_pen)
        p.drawLine(int(ws_x + 4), int(cy), int(ws_x + ws_w - 4), int(cy))
        p.drawLine(int(cx), int(ws_y + 4), int(cx), int(ws_y + ws_h - 4))

        # Centre crosshair
        ch_size = 6
        ch_pen = QPen(QColor(34, 184, 207, 60), 1)
        p.setPen(ch_pen)
        p.drawLine(int(cx - ch_size), int(cy), int(cx + ch_size), int(cy))
        p.drawLine(int(cx), int(cy - ch_size), int(cx), int(cy + ch_size))

    def _draw_labels(self, p, ws_x, ws_y, ws_w, ws_h, margin):
        cx = ws_x + ws_w / 2

        # Edge labels
        label_font = QFont("Segoe UI", 7)
        label_font.setWeight(QFont.Medium)
        p.setFont(label_font)
        p.setPen(QColor("#3d5268"))
        p.drawText(int(cx - 8), int(ws_y - 5), "TOP")
        p.drawText(int(cx - 15), int(ws_y + ws_h + 13), "BOTTOM")
        p.drawText(max(2, int(ws_x - 22)), int(ws_y + ws_h / 2 + 3), "L")
        p.drawText(min(self.width() - 12, int(ws_x + ws_w + 6)), int(ws_y + ws_h / 2 + 3), "R")

        # Title
        p.setPen(QColor("#6b8299"))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(max(6, int(ws_x)), margin + 14, "WINDSHIELD FRONT VIEW")

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
        # Outer halo (large, soft)
        outer_r = 36.0
        halo = QRadialGradient(center, outer_r)
        halo.setColorAt(0.0, QColor(255, 200, 50, 0))
        halo.setColorAt(0.3, QColor(255, 180, 30, 60))
        halo.setColorAt(0.6, QColor(255, 140, 0, 40))
        halo.setColorAt(1.0, QColor(255, 87, 34, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(center, outer_r, outer_r)

        # Inner glow (intense core)
        inner_r = 14.0
        glow = QRadialGradient(center, inner_r)
        glow.setColorAt(0.0, QColor(255, 255, 220, 255))
        glow.setColorAt(0.5, QColor(255, 220, 80, 200))
        glow.setColorAt(1.0, QColor(255, 160, 0, 0))
        p.setBrush(QBrush(glow))
        p.drawEllipse(center, inner_r, inner_r)

        # Core dot
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawEllipse(center, 3, 3)

    @staticmethod
    def _draw_out_of_bounds_spot(p, center, ws_x, ws_y, ws_w, ws_h):
        # Pulsing red indicator
        p.setPen(QPen(QColor(248, 113, 113, 160), 2, Qt.DashLine))
        p.setBrush(QColor(248, 113, 113, 30))
        p.drawEllipse(center, 10, 10)

        # Line to nearest windshield edge
        p.setPen(QPen(QColor(248, 113, 113, 70), 1, Qt.DotLine))
        clamped_x = max(ws_x, min(ws_x + ws_w, center.x()))
        clamped_y = max(ws_y, min(ws_y + ws_h, center.y()))
        p.drawLine(int(clamped_x), int(clamped_y), int(center.x()), int(center.y()))
