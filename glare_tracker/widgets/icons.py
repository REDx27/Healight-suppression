"""Dependency-free vector icons used throughout the desktop interface."""

from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


class IconFactory:
    """Render a small, consistent line-icon set with Qt primitives."""

    DEFAULT_COLOR = "#8fa8bf"

    @classmethod
    def icon(cls, name: str, color: str | QColor | None = None, size: int = 20) -> QIcon:
        pixmap = cls.pixmap(name, color, size)
        return QIcon(pixmap)

    @classmethod
    def pixmap(cls, name: str, color: str | QColor | None = None, size: int = 20) -> QPixmap:
        color = QColor(color or cls.DEFAULT_COLOR)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(size / 24.0, size / 24.0)
        pen = QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cls._draw(painter, name, color)
        painter.end()
        return pixmap

    @staticmethod
    def _draw(p: QPainter, name: str, color: QColor):
        if name == "play":
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(7, 4), QPointF(19, 12), QPointF(7, 20)]))
        elif name == "stop":
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
        elif name == "target":
            p.drawEllipse(QPointF(12, 12), 7, 7)
            p.drawEllipse(QPointF(12, 12), 2.5, 2.5)
            p.drawLine(QPointF(12, 2), QPointF(12, 6))
            p.drawLine(QPointF(12, 18), QPointF(12, 22))
            p.drawLine(QPointF(2, 12), QPointF(6, 12))
            p.drawLine(QPointF(18, 12), QPointF(22, 12))
        elif name == "reset":
            p.drawArc(QRectF(4, 4, 16, 16), 35 * 16, 285 * 16)
            p.drawLine(QPointF(4.5, 5), QPointF(4.5, 10))
            p.drawLine(QPointF(4.5, 5), QPointF(9.5, 5))
        elif name == "panel":
            p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
            p.drawLine(QPointF(15, 5), QPointF(15, 19))
            p.drawLine(QPointF(18, 9), QPointF(18, 15))
        elif name == "settings":
            points = []
            for index in range(24):
                angle = -math.pi / 2 + index * math.pi / 12
                radius = 9.2 if index % 3 == 0 else 7.2
                points.append(QPointF(
                    12 + math.cos(angle) * radius,
                    12 + math.sin(angle) * radius,
                ))
            p.drawPolygon(QPolygonF(points))
            p.setBrush(color)
            p.drawEllipse(QPointF(12, 12), 2.7, 2.7)
        elif name == "eye":
            path = QPainterPath(QPointF(3, 12))
            path.cubicTo(7, 5.5, 17, 5.5, 21, 12)
            path.cubicTo(17, 18.5, 7, 18.5, 3, 12)
            p.drawPath(path)
            p.setBrush(color)
            p.drawEllipse(QPointF(12, 12), 2.7, 2.7)
        elif name == "light":
            p.drawEllipse(QPointF(12, 12), 4, 4)
            for a, b in [((12, 2), (12, 5)), ((12, 19), (12, 22)),
                         ((2, 12), (5, 12)), ((19, 12), (22, 12)),
                         ((5, 5), (7.2, 7.2)), ((16.8, 16.8), (19, 19)),
                         ((19, 5), (16.8, 7.2)), ((7.2, 16.8), (5, 19))]:
                p.drawLine(QPointF(*a), QPointF(*b))
        elif name == "operations":
            p.drawPolyline(QPolygonF([
                QPointF(2, 13), QPointF(6, 13), QPointF(8.5, 7),
                QPointF(12, 18), QPointF(15, 10), QPointF(17, 13), QPointF(22, 13),
            ]))
        elif name == "controls":
            for y, x in [(6, 8), (12, 16), (18, 11)]:
                p.drawLine(QPointF(3, y), QPointF(21, y))
                p.setBrush(color)
                p.drawEllipse(QPointF(x, y), 2, 2)
                p.setBrush(Qt.NoBrush)
        elif name == "camera":
            p.drawRoundedRect(QRectF(3, 7, 18, 12), 2, 2)
            p.drawEllipse(QPointF(12, 13), 3.5, 3.5)
            p.drawLine(QPointF(7, 7), QPointF(9, 4.5))
            p.drawLine(QPointF(9, 4.5), QPointF(15, 4.5))
            p.drawLine(QPointF(15, 4.5), QPointF(17, 7))
        elif name == "road":
            p.drawLine(QPointF(8, 21), QPointF(11, 3))
            p.drawLine(QPointF(16, 21), QPointF(13, 3))
            p.drawLine(QPointF(12, 20), QPointF(12, 16))
            p.drawLine(QPointF(12, 12), QPointF(12, 9))
        else:
            p.drawRoundedRect(QRectF(4, 4, 16, 16), 3, 3)


ICON_SIZE = QSize(18, 18)
