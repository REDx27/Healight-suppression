"""Compact collapsible property panel inspired by Blender's editor panels."""

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QGroupBox, QSizePolicy


class PropertyGroupBox(QGroupBox):
    """A QGroupBox with an integrated, clickable property-panel header.

    The widget intentionally remains a QGroupBox so existing visibility and
    layout code keeps working.  Collapsing clips the content instead of
    changing child visibility, preserving controls that are conditionally
    hidden by the active operating mode.
    """

    HEADER_HEIGHT = 25

    def __init__(self, title: str, parent=None):
        self._panel_title = str(title)
        super().__init__("", parent)
        self._expanded = True
        self._header_hovered = False
        self.setProperty("propertyPanel", True)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setAccessibleName(f"{self._panel_title} settings panel")
        self.setToolTip("Click the panel header to collapse or expand")

    def title(self) -> str:
        return self._panel_title

    def setTitle(self, title: str):
        self._panel_title = str(title)
        self.setAccessibleName(f"{self._panel_title} settings panel")
        self.update()

    def isExpanded(self) -> bool:
        return self._expanded

    def setExpanded(self, expanded: bool):
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        if expanded:
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
        else:
            self.setFixedHeight(self.HEADER_HEIGHT + 2)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        if not self._expanded:
            return QSize(super().sizeHint().width(), self.HEADER_HEIGHT + 2)
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        if not self._expanded:
            return QSize(80, self.HEADER_HEIGHT + 2)
        return super().minimumSizeHint()

    def mouseMoveEvent(self, event):
        hovered = event.pos().y() <= self.HEADER_HEIGHT
        if hovered != self._header_hovered:
            self._header_hovered = hovered
            self.update(0, 0, self.width(), self.HEADER_HEIGHT + 1)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._header_hovered:
            self._header_hovered = False
            self.update(0, 0, self.width(), self.HEADER_HEIGHT + 1)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.LeftButton
            and event.pos().y() <= self.HEADER_HEIGHT
        ):
            self.setExpanded(not self._expanded)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        header = QRectF(1, 1, max(0, self.width() - 2), self.HEADER_HEIGHT)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#3b3d41" if self._header_hovered else "#35373b"))
        painter.drawRoundedRect(header, 3, 3)
        painter.fillRect(
            QRectF(1, self.HEADER_HEIGHT - 4, max(0, self.width() - 2), 5),
            QColor("#3b3d41" if self._header_hovered else "#35373b"),
        )
        painter.setPen(QPen(QColor("#242529"), 1))
        painter.drawLine(
            QPointF(1, self.HEADER_HEIGHT + 0.5),
            QPointF(self.width() - 1, self.HEADER_HEIGHT + 0.5),
        )

        # Disclosure chevron.
        chevron = QPainterPath()
        if self._expanded:
            chevron.moveTo(9, 10)
            chevron.lineTo(13, 14)
            chevron.lineTo(17, 10)
        else:
            chevron.moveTo(11, 8)
            chevron.lineTo(15, 12)
            chevron.lineTo(11, 16)
        painter.setPen(QPen(QColor("#aeb1b5"), 1.35, Qt.SolidLine,
                            Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(chevron)

        font = QFont(self.font())
        font.setPointSizeF(8.2)
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        painter.setPen(QColor("#d0d2d5"))
        painter.drawText(
            QRectF(23, 1, max(0, self.width() - 52), self.HEADER_HEIGHT),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._panel_title,
        )

        # Six-dot drag/detail grip from Blender panel headers. It is a visual
        # affordance only; panel ordering is fixed by the application workflow.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#73777c"))
        start_x = self.width() - 14
        for row in range(2):
            for column in range(3):
                painter.drawEllipse(
                    QPointF(start_x + column * 3, 10 + row * 4), 0.75, 0.75)

        painter.end()
