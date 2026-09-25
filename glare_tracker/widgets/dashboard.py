"""Reusable dashboard components for the GlareTracker operator interface."""

from __future__ import annotations

from PyQt5.QtCore import QElapsedTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QBoxLayout, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QTabWidget,
    QToolButton, QVBoxLayout, QWidget,
)


class StatusBadge(QLabel):
    """Compact semantic status indicator styled through a Qt property."""

    def __init__(self, text: str, state: str = "idle", parent=None):
        super().__init__(text, parent)
        self.setObjectName("statusBadge")
        self.setAlignment(Qt.AlignCenter)
        self._state = ""
        self.set_status(text, state)

    def set_status(self, text: str, state: str = "idle"):
        if text == self.text() and state == self._state:
            return
        self._state = state
        self.setText(text)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class CameraPreviewCard(QFrame):
    """Self-contained camera viewport with throttled rendering and status."""

    def __init__(self, title: str, placeholder: str, parent=None):
        super().__init__(parent)
        self.setObjectName("cameraCard")
        # Let the card expand vertically when the sidebar is tall
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._last_image: QImage | None = None
        self._render_clock = QElapsedTimer()
        self._render_clock.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("cameraTitle")
        self.status_badge = StatusBadge("STOPPED")
        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(self.status_badge)

        self.viewport = QLabel(placeholder)
        self.viewport.setObjectName("cameraViewport")
        self.viewport.setAlignment(Qt.AlignCenter)
        self.viewport.setMinimumSize(120, 80)
        # No fixed max height — viewport stretches with the card
        self.viewport.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.detail = QLabel("Waiting for camera")
        self.detail.setObjectName("mutedText")
        self.detail.setWordWrap(True)

        layout.addLayout(title_row)
        layout.addWidget(self.viewport, 1)  # stretch factor 1
        layout.addWidget(self.detail)

    def set_frame(self, image: QImage):
        if self._render_clock.elapsed() < 50:
            return
        self._render_clock.restart()
        self._last_image = image
        self._render_image()

    def set_status(self, message: str, state: str):
        labels = {
            "active": "ONLINE", "warning": "SEARCHING", "error": "OFFLINE",
            "info": "MANUAL", "idle": "STOPPED",
        }
        self.status_badge.set_status(labels.get(state, state.upper()), state)
        self.detail.setText(message)

    def set_placeholder(self, text: str):
        self._last_image = None
        self.viewport.clear()
        self.viewport.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_image()

    def _render_image(self):
        if self._last_image is None or self.viewport.width() < 2:
            return
        pixmap = QPixmap.fromImage(self._last_image)
        self.viewport.setPixmap(pixmap.scaled(
            self.viewport.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class ApplicationHeader(QFrame):
    """Application identity and high-level operating state."""

    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.setObjectName("appHeader")
        self.setFixedHeight(72)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        title = QLabel("GlareTracker")
        title.setObjectName("appTitle")
        subtitle = QLabel(f"ACTIVE GLARE SUPPRESSION  //  v{version}")
        subtitle.setObjectName("appSubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)

        self.mode_badge = StatusBadge("MANUAL", "info")
        self.tracking_badge = StatusBadge("SYSTEM IDLE", "idle")
        self.panel_toggle = QToolButton()
        self.panel_toggle.setObjectName("panelToggle")
        self.panel_toggle.setText("PANEL")
        self.panel_toggle.setToolTip("Show or hide the operations sidebar")
        self.panel_toggle.setCheckable(True)
        self.panel_toggle.setChecked(True)
        layout.addLayout(title_stack)
        layout.addStretch()
        layout.addWidget(self.panel_toggle)
        layout.addSpacing(8)
        layout.addWidget(self.mode_badge)
        layout.addSpacing(8)
        layout.addWidget(self.tracking_badge)

    def set_mode(self, automatic: bool):
        self.mode_badge.set_status(
            "AUTO VISION" if automatic else "MANUAL", "active" if automatic else "info")

    def set_tracking(self, text: str, state: str):
        self.tracking_badge.set_status(text, state)


class CameraFeedPanel(QWidget):
    """Pair of consistently styled driver and road-facing camera cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        heading = QLabel("VISION INPUTS")
        heading.setObjectName("appSubtitle")
        self._cards = QBoxLayout(QBoxLayout.LeftToRight)
        self._cards.setSpacing(8)
        self.driver = CameraPreviewCard("DRIVER / EYES", "Driver camera")
        self.headlight = CameraPreviewCard("ROAD / LIGHT", "Manual coordinates")
        self._cards.addWidget(self.driver)
        self._cards.addWidget(self.headlight)
        layout.addWidget(heading)
        layout.addLayout(self._cards)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = (
            QBoxLayout.TopToBottom if self.width() < 390
            else QBoxLayout.LeftToRight
        )
        if self._cards.direction() != direction:
            self._cards.setDirection(direction)


class SceneWorkspace(QFrame):
    """Own the primary 3D scene and its responsive windshield overlay."""

    def __init__(self, scene: QWidget, overlay: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("workspaceFrame")
        self.scene = scene
        self.overlay = overlay
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(scene)
        overlay.setParent(self)
        overlay.setToolTip("Live windshield intersection view")
        overlay.show()
        overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Scale the overlay proportionally but with sensible bounds
        width = min(420, max(240, int(self.width() * 0.32)))
        height = int(width * 0.58)
        margin = 12
        self.overlay.setGeometry(margin, margin, width, height)
        self.overlay.raise_()


class OperationsSidebar(QTabWidget):
    """Tabbed sidebar separating live operations from configuration."""

    def __init__(self, overview_widgets: list[QWidget], controls: QWidget, parent=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.addTab(self._scroll_page(overview_widgets), "OPERATIONS")
        self.addTab(self._scroll_page([controls]), "CONFIGURATION")

    @staticmethod
    def _scroll_page(widgets: list[QWidget]) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(10)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll
