"""Windows command symbols and application-specific line icons."""

from __future__ import annotations

import math
from pathlib import Path
import sys
from functools import lru_cache

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import (
    QColor, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath, QPen,
    QPixmap, QPolygonF, QRawFont,
)
from PyQt5.QtWidgets import (
    QApplication, QPushButton, QStyle, QSizePolicy, QStyleOptionButton, QStylePainter,
)


ICON_SIZE = QSize(16, 16)

_MATERIAL_ICONS = {"user": "person", "bulb": "lightbulb",
                   "monitor": "desktop_windows", "research": "biotech"}
_ICON_ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "assets" / "icons" / "material"

# Segoe Fluent Icons and Segoe MDL2 Assets share these Windows symbol codes.
_WINDOWS_SYMBOLS = {
    "play": 0xE768,
    "pause": 0xE769,
    "stop": 0xE71A,
    "reset": 0xE72C,
    "panel": 0xE8A0,
    "settings": 0xE713,
    "eye": 0xE890,
    "camera": 0xE722,
    "display": 0xE7F4,
    "save": 0xE74E,
    "delete": 0xE74D,
    "lock": 0xE72E,
    "unlock": 0xE785,
    "help": 0xE897,
    "print": 0xE749,
    "undo": 0xE7A7,
    "close": 0xE711,
    "fit": 0xE8FB,
    "folder": 0xE8B7,
    "connect": 0xE703,
    "next": 0xE76C,
    "back": 0xE76B,
}

_QT_FALLBACKS = {
    "pause": QStyle.SP_MediaPause,
    "display": QStyle.SP_DesktopIcon,
    "help": QStyle.SP_DialogHelpButton,
    "undo": QStyle.SP_ArrowBack,
    "close": QStyle.SP_DialogCloseButton,
    "fit": QStyle.SP_DialogApplyButton,
    "folder": QStyle.SP_DirOpenIcon,
    "connect": QStyle.SP_DriveNetIcon,
    "next": QStyle.SP_ArrowRight,
    "back": QStyle.SP_ArrowLeft,
}


class IconFactory:
    """Render standard system glyphs with Qt-compatible fallbacks."""

    DEFAULT_COLOR = "#dbe3ed"

    @classmethod
    def icon(cls, name: str, color: str | QColor | None = None, size: int = 16) -> QIcon:
        result = QIcon()
        for scale in (1, 2):
            pixmap = cls.pixmap(name, color, size * scale)
            pixmap.setDevicePixelRatio(scale)
            result.addPixmap(pixmap)
        return result

    @classmethod
    def pixmap(cls, name: str, color: str | QColor | None = None, size: int = 20) -> QPixmap:
        color = QColor(color or cls.DEFAULT_COLOR)
        return QPixmap(cls._cached_pixmap(name, color.rgba(), int(size)))

    @classmethod
    @lru_cache(maxsize=128)
    def _cached_pixmap(cls, name: str, rgba: int, size: int) -> QPixmap:
        """Render each vector/color/size combination once per process."""

        color = QColor.fromRgba(rgba)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        glyph = _WINDOWS_SYMBOLS.get(name)
        family = cls._symbol_font(glyph) if glyph is not None else None
        if name in _MATERIAL_ICONS:
            renderer = QSvgRenderer(str(_ICON_ASSETS / f"{_MATERIAL_ICONS[name]}.svg"))
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
        elif family:
            font = QFont(family)
            font.setPixelSize(max(1, round(size * 0.92)))
            painter.setFont(font)
            painter.setPen(color)
            symbol = chr(glyph)
            bounds = QFontMetricsF(font).tightBoundingRect(symbol)
            centre = QPointF(size / 2, size / 2) - bounds.center()
            painter.drawText(centre, symbol)
        elif name in _QT_FALLBACKS:
            icon = QApplication.style().standardIcon(_QT_FALLBACKS[name])
            icon.paint(painter, pixmap.rect())
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
        else:
            painter.scale(size / 24.0, size / 24.0)
            painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            cls._draw(painter, name, color)
        painter.end()
        return pixmap

    @staticmethod
    @lru_cache(maxsize=len(_WINDOWS_SYMBOLS))
    def _symbol_font(glyph: int) -> str | None:
        for family in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            font = QRawFont.fromFont(QFont(family))
            if font.familyName().casefold() == family.casefold() and font.supportsCharacter(glyph):
                return family
        return None

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
            p.drawEllipse(QPointF(12, 12), 7.2, 7.2)
            p.drawEllipse(QPointF(12, 12), 2.5, 2.5)
            for index in range(8):
                angle = index * math.pi / 4
                p.drawLine(
                    QPointF(12 + math.cos(angle) * 7.2,
                            12 + math.sin(angle) * 7.2),
                    QPointF(12 + math.cos(angle) * 10.2,
                            12 + math.sin(angle) * 10.2),
                )
        elif name == "sun":
            p.drawEllipse(QPointF(12, 12), 4.2, 4.2)
            for index in range(8):
                angle = index * math.pi / 4
                p.drawLine(
                    QPointF(12 + math.cos(angle) * 7.0,
                            12 + math.sin(angle) * 7.0),
                    QPointF(12 + math.cos(angle) * 10.0,
                            12 + math.sin(angle) * 10.0),
                )
        elif name == "moon":
            moon = QPainterPath()
            moon.addEllipse(QPointF(11, 12), 8, 8)
            cutout = QPainterPath()
            cutout.addEllipse(QPointF(15, 9), 7, 7)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawPath(moon.subtracted(cutout))
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
        elif name == "grid":
            p.drawRoundedRect(QRectF(3, 3, 18, 18), 1.5, 1.5)
            for value in (8, 13, 18):
                p.drawLine(QPointF(3, value), QPointF(21, value))
                p.drawLine(QPointF(value, 3), QPointF(value, 21))
        elif name == "save":
            p.drawRoundedRect(QRectF(4, 3, 16, 18), 1.5, 1.5)
            p.drawRect(QRectF(7, 3, 9, 6))
            p.drawRoundedRect(QRectF(7, 13, 10, 6), 1.2, 1.2)
            p.drawLine(QPointF(14, 4.5), QPointF(14, 7.5))
        elif name == "print":
            p.drawRoundedRect(QRectF(3, 8, 18, 9), 2, 2)
            p.drawRect(QRectF(7, 3, 10, 5))
            p.drawRect(QRectF(7, 14, 10, 7))
        elif name in ("delete", "remove"):
            p.drawRoundedRect(QRectF(7, 7, 10, 14), 1.5, 1.5)
            p.drawLine(QPointF(5, 7), QPointF(19, 7))
            p.drawLine(QPointF(9, 4), QPointF(15, 4))
            p.drawLine(QPointF(9.5, 10), QPointF(10.5, 18))
            p.drawLine(QPointF(14.5, 10), QPointF(13.5, 18))
        elif name in ("lock", "unlock"):
            p.drawRoundedRect(QRectF(6, 10, 12, 10), 1.8, 1.8)
            shackle = QPainterPath()
            if name == "lock":
                shackle.moveTo(8.5, 10)
                shackle.lineTo(8.5, 7.5)
                shackle.cubicTo(8.5, 2.8, 15.5, 2.8, 15.5, 7.5)
                shackle.lineTo(15.5, 10)
            else:
                shackle.moveTo(15.5, 10)
                shackle.lineTo(15.5, 7.5)
                shackle.cubicTo(15.5, 3.2, 9, 3.2, 9, 7.5)
            p.drawPath(shackle)
            p.setBrush(color)
            p.drawEllipse(QPointF(12, 15), 1.2, 1.2)
        else:
            p.drawRoundedRect(QRectF(4, 4, 16, 16), 3, 3)


class CommandButton(QPushButton):
    """A standard Qt command that can shrink gracefully inside a property pane."""

    def __init__(self, text):
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(min(80, hint.width()))
        return hint

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        if self.width() < self.sizeHint().width():
            contents = self.style().subElementRect(QStyle.SE_PushButtonContents, option, self)
            icon_width = option.iconSize.width() + 4 if not option.icon.isNull() else 0
            option.text = self.fontMetrics().elidedText(
                option.text, Qt.ElideRight, max(0, contents.width() - icon_width))
        painter = QStylePainter(self)
        painter.drawControl(QStyle.CE_PushButton, option)


def command_button(
    text: str, icon: str, *, tooltip: str = "", role: str = "",
    color: str | None = None,
) -> QPushButton:
    """Create a labeled command using the app's shared icon size and style."""
    button = CommandButton(text)
    button.setIcon(IconFactory.icon(icon, color))
    button.setIconSize(ICON_SIZE)
    if tooltip:
        button.setToolTip(tooltip)
    if role:
        button.setProperty("commandRole", role)
    return button
