"""Compact animated toggle used for binary operator settings."""

from PyQt5.QtCore import (
    QEasingCurve, QEvent, QPropertyAnimation, QRect, QRectF, QSize, Qt, pyqtProperty,
)
from PyQt5.QtGui import QColor, QCursor, QPainter, QPen
from PyQt5.QtWidgets import QCheckBox, QSizePolicy


class ToggleSwitch(QCheckBox):
    """A keyboard-accessible QCheckBox rendered as a modern toggle switch."""

    TRACK_WIDTH = 28
    TRACK_HEIGHT = 14
    KNOB_MARGIN = 2
    TEXT_GAP = 8

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._position = 1.0 if self.isChecked() else 0.0
        self._hovered = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(24)
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Expanding)
        policy.setVerticalPolicy(QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setAttribute(Qt.WA_Hover, True)
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(130)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.stateChanged.connect(self._animate_state)

    def sizeHint(self):
        metrics = self.fontMetrics()
        width = self.TRACK_WIDTH
        if self.text():
            width += self.TEXT_GAP + metrics.horizontalAdvance(self.text())
        return QSize(width + 2, max(24, metrics.height() + 6))

    def minimumSizeHint(self):
        hint = self.sizeHint()
        return QSize(min(hint.width(), 140), hint.height())

    def heightForWidth(self, width):
        text_width = max(1, width - self.TRACK_WIDTH - self.TEXT_GAP)
        bounds = self.fontMetrics().boundingRect(
            QRect(0, 0, text_width, 0), Qt.TextWordWrap, self.text())
        return max(24, bounds.height() + 6)

    def hitButton(self, position):
        return self.rect().contains(position)

    def event(self, event):
        if event.type() == QEvent.HoverEnter:
            self._hovered = True
            self.update()
        elif event.type() == QEvent.HoverLeave:
            self._hovered = False
            self.update()
        return super().event(event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        track_y = (self.height() - self.TRACK_HEIGHT) / 2.0
        track = QRectF(1.0, track_y, self.TRACK_WIDTH, self.TRACK_HEIGHT)
        if not self.isEnabled():
            track_color = QColor("#34363a")
            knob_color = QColor("#777b80")
            text_color = QColor("#929aa5")
        elif self.isChecked():
            track_color = QColor("#4779bd" if self._hovered else "#3b6cae")
            knob_color = QColor("#f3f6fa")
            text_color = QColor("#edf0f4")
        else:
            track_color = QColor("#555a60" if self._hovered else "#464a4f")
            knob_color = QColor("#c8cbd0")
            text_color = QColor("#edf0f4")

        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        radius = self.TRACK_HEIGHT / 2.0
        painter.drawRoundedRect(track, radius, radius)

        knob_size = self.TRACK_HEIGHT - 2 * self.KNOB_MARGIN
        travel = self.TRACK_WIDTH - knob_size - 2 * self.KNOB_MARGIN
        knob_x = 1.0 + self.KNOB_MARGIN + travel * self._position
        knob = QRectF(knob_x, track_y + self.KNOB_MARGIN, knob_size, knob_size)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob)

        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#abd4ff"), 1))
            painter.drawRoundedRect(QRectF(self.rect().adjusted(0, 1, -1, -1)), 4, 4)

        if self.text():
            text_rect = self.rect().adjusted(
                self.TRACK_WIDTH + self.TEXT_GAP, 0, 0, 0)
            painter.setPen(text_color)
            painter.drawText(
                text_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, self.text())

    def _animate_state(self, state):
        target = 1.0 if state == Qt.Checked else 0.0
        if not self.isVisible():
            self._animation.stop()
            self._set_position(target)
            return
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(target)
        self._animation.start()

    def _get_position(self):
        return self._position

    def _set_position(self, value):
        self._position = min(1.0, max(0.0, float(value)))
        self.update()

    position = pyqtProperty(float, _get_position, _set_position)
