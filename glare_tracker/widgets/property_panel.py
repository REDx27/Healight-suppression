"""Compact collapsible property panel inspired by Blender's editor panels."""

from PyQt5.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QGroupBox, QSizePolicy, QWidget
from glare_tracker.styles import PANEL_HEADER_HEIGHT


class PropertyGroupBox(QGroupBox):
    """A QGroupBox with an integrated, clickable property-panel header.

    The widget intentionally remains a QGroupBox so existing visibility and
    layout code keeps working.  Collapsing clips the content instead of
    changing child visibility, preserving controls that are conditionally
    hidden by the active operating mode.
    """

    HEADER_HEIGHT = PANEL_HEADER_HEIGHT

    def __init__(self, title: str, parent=None):
        self._panel_title = str(title)
        super().__init__("", parent)
        self._expanded = True
        self._header_hovered = False
        self._saved_focus_policies = {}
        self.setFocusPolicy(Qt.StrongFocus)
        self.setProperty("propertyPanel", True)
        self.setMouseTracking(True)
        # Maximum caps height at the unconstrained sizeHint and clips wrapped
        # text. Preferred lets the page honor heightForWidth; its trailing
        # stretch still keeps every section anchored at the top.
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setAccessibleName(f"{self._panel_title} settings panel")
        self.setToolTip(f"{self._panel_title}. Click the header to collapse or expand.")

    def title(self) -> str:
        return self._panel_title

    def setTitle(self, title: str):
        self._panel_title = str(title)
        self.setAccessibleName(f"{self._panel_title} settings panel")
        self.setToolTip(f"{self._panel_title}. Click the header to collapse or expand.")
        self.update()

    def isExpanded(self) -> bool:
        return self._expanded

    def setExpanded(self, expanded: bool):
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        if expanded:
            for child, policy in self._saved_focus_policies.items():
                child.setFocusPolicy(policy)
            self._saved_focus_policies.clear()
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
        else:
            focused = QApplication.focusWidget()
            if focused is not None and self.isAncestorOf(focused):
                self.setFocus()
            for child in self.findChildren(QWidget):
                self._saved_focus_policies[child] = child.focusPolicy()
                child.setFocusPolicy(Qt.NoFocus)
            self.setFixedHeight(self.HEADER_HEIGHT + 2)
        self.setAccessibleDescription("Expanded" if expanded else "Collapsed. Press Space to expand.")
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

    def hasHeightForWidth(self):
        return self._expanded and self.layout() is not None and self.layout().hasHeightForWidth()

    def heightForWidth(self, width):
        if not self._expanded:
            return self.HEADER_HEIGHT + 2
        if self.layout() is not None and self.layout().hasHeightForWidth():
            return self.layout().totalHeightForWidth(width)
        return super().sizeHint().height()

    def event(self, event):
        # QGroupBox consumes activation keys for its built-in checkbox before
        # QWidget dispatches keyPressEvent. Our disclosure header owns them.
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if not event.isAutoRepeat():
                self.keyPressEvent(event)
            return True
        handled = super().event(event)
        if event.type() == QEvent.LayoutRequest:
            # Wrapped notes and conditional rows can change height without a
            # resize. Tell the surrounding scroll page to recalculate as well.
            self.updateGeometry()
        return handled

    def mouseMoveEvent(self, event):
        hovered = event.pos().y() <= self.HEADER_HEIGHT
        if hovered != self._header_hovered:
            self._header_hovered = hovered
            self.update(0, 0, self.width(), self.HEADER_HEIGHT + 1)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.setExpanded(not self._expanded)
            event.accept()
            return
        super().keyPressEvent(event)

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
        painter.setBrush(QColor("#383b40" if self._header_hovered else "#32353a"))
        painter.drawRoundedRect(header, 4, 4)
        painter.fillRect(
            QRectF(1, self.HEADER_HEIGHT - 4, max(0, self.width() - 2), 5),
            QColor("#383b40" if self._header_hovered else "#32353a"),
        )
        painter.setPen(QPen(QColor("#242529"), 1))
        painter.drawLine(
            QPointF(1, self.HEADER_HEIGHT + 0.5),
            QPointF(self.width() - 1, self.HEADER_HEIGHT + 0.5),
        )

        # Disclosure chevron.
        chevron = QPainterPath()
        if self._expanded:
            chevron.moveTo(11, 12)
            chevron.lineTo(15, 16)
            chevron.lineTo(19, 12)
        else:
            chevron.moveTo(13, 10)
            chevron.lineTo(17, 14)
            chevron.lineTo(13, 18)
        painter.setPen(QPen(QColor("#aeb1b5"), 1.35, Qt.SolidLine,
                            Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(chevron)

        font = QFont(self.font())
        font.setFamily("Segoe UI")
        font.setPixelSize(12)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#d9dde3"))
        width = max(0, self.width() - 40)
        painter.drawText(
            QRectF(27, 1, width, self.HEADER_HEIGHT),
            Qt.AlignLeft | Qt.AlignVCenter,
            QFontMetrics(font).elidedText(self._panel_title, Qt.ElideRight, width),
        )

        if self.hasFocus():
            painter.setPen(QPen(QColor("#78a9e6"), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(header.adjusted(1, 1, -1, -1), 3, 3)
        painter.end()
