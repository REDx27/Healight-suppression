"""Reusable dashboard components for the GlareTracker operator interface."""

from __future__ import annotations

from PyQt5.QtCore import QElapsedTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QBoxLayout, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLayout, QScrollArea,
    QSizePolicy, QTabWidget, QPushButton, QTabBar, QToolButton, QVBoxLayout, QWidget,
)

from glare_tracker.widgets.icons import ICON_SIZE, IconFactory


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

    def __init__(self, title: str, placeholder: str, icon_name: str = "camera", parent=None):
        super().__init__(parent)
        self.setObjectName("cameraCard")
        feed = "road" if icon_name == "road" else "driver"
        self.setProperty("feed", feed)
        # Cards share the bounded bottom preview strip. The source pixmap must
        # not be allowed to turn its native resolution into a layout request.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(280)
        self.setMaximumWidth(480)
        self._last_image: QImage | None = None
        self._render_clock = QElapsedTimer()
        self._render_clock.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(IconFactory.pixmap(icon_name, "#64a8ef", 16))
        title_label = QLabel(title)
        title_label.setObjectName("cameraTitle")
        self.status_badge = StatusBadge("STOPPED")
        title_row.addWidget(title_icon)
        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(self.status_badge)

        self.viewport = QLabel(placeholder)
        self.viewport.setObjectName("cameraViewport")
        self.viewport.setAlignment(Qt.AlignCenter)
        self.viewport.setMinimumSize(120, 80)
        # No fixed max height — viewport stretches with the card
        self.viewport.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.detail = QLabel("Waiting for camera")
        self.detail.setObjectName("mutedText")
        self.detail.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
        layout.setSizeConstraint(QLayout.SetNoConstraint)
        layout.setContentsMargins(18, 8, 18, 8)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        title = QLabel("GlareTracker")
        title.setObjectName("appTitle")
        self.subtitle = QLabel(f"ACTIVE GLARE SUPPRESSION  //  v{version}")
        self.subtitle.setObjectName("appSubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(self.subtitle)

        self.mode_badge = StatusBadge("FULLY AUTO", "active")
        self.tracking_badge = StatusBadge("SYSTEM IDLE", "idle")

        self.session_buttons = QButtonGroup(self)
        self.session_buttons.setExclusive(True)
        self.btn_run = self._session_button(
            "Run", "run", "Start required cameras and real-time calculations")
        self.btn_standby = self._session_button(
            "Standby", "standby", "Show required camera previews without calculations")
        self.btn_stop = self._session_button(
            "Stop", "stop", "Stop calculations and release all cameras")
        self.btn_stop.setChecked(True)
        for button in (self.btn_run, self.btn_standby, self.btn_stop):
            self.session_buttons.addButton(button)

        self.btn_calibrate = QPushButton("Calibrate Center")
        self.btn_calibrate.setObjectName("headerAction")
        self.btn_calibrate.setProperty("role", "calibrate")
        self.btn_calibrate.setIcon(IconFactory.icon("target", "#75b7f5"))
        self.btn_calibrate.setIconSize(ICON_SIZE)
        self.btn_calibrate.setToolTip("Use the current eye position as the center reference")

        self.btn_reset_view = QPushButton("Reset View")
        self.btn_reset_view.setObjectName("headerAction")
        self.btn_reset_view.setProperty("role", "reset")
        self.btn_reset_view.setIcon(IconFactory.icon("reset", "#a8b6c1"))
        self.btn_reset_view.setIconSize(ICON_SIZE)
        self.btn_reset_view.setToolTip("Restore the default 3D camera angle")

        self.panel_toggle = QToolButton()
        self.panel_toggle.setObjectName("panelToggle")
        self.panel_toggle.setText("PANEL")
        self.panel_toggle.setIcon(IconFactory.icon("panel"))
        self.panel_toggle.setIconSize(ICON_SIZE)
        self.panel_toggle.setToolTip("Show or hide the operations sidebar")
        self.panel_toggle.setCheckable(True)
        self.panel_toggle.setChecked(True)
        layout.addLayout(title_stack)
        layout.addStretch()
        layout.addWidget(self.btn_run)
        layout.addWidget(self.btn_standby)
        layout.addWidget(self.btn_stop)
        layout.addSpacing(4)
        layout.addWidget(self.btn_calibrate)
        layout.addWidget(self.btn_reset_view)
        layout.addSpacing(10)
        layout.addWidget(self.panel_toggle)
        layout.addSpacing(8)
        layout.addWidget(self.mode_badge)
        layout.addSpacing(8)
        layout.addWidget(self.tracking_badge)

    def _session_button(self, text: str, role: str, tooltip: str):
        button = QPushButton(text)
        button.setObjectName("sessionStateAction")
        button.setProperty("sessionRole", role)
        button.setCheckable(True)
        button.setToolTip(tooltip)
        if role == "run":
            button.setIcon(IconFactory.icon("play", "#dffaff"))
        elif role == "stop":
            button.setIcon(IconFactory.icon("stop", "#fff1f2"))
        button.setIconSize(ICON_SIZE)
        return button

    def set_mode(self, mode_text: str):
        compact = mode_text.replace(" Position", "").upper()
        state = "active" if mode_text == "Fully Auto" else "info"
        self.mode_badge.set_status(compact, state)

    def set_session_state(self, state: str):
        mapping = {
            "Run": self.btn_run,
            "Standby": self.btn_standby,
            "Stop": self.btn_stop,
        }
        button = mapping[state]
        button.setChecked(True)

    def set_tracking(self, text: str, state: str):
        self.tracking_badge.set_status(text, state)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 1260
        very_compact = self.width() < 820
        self.btn_calibrate.setText("" if compact else "Calibrate Center")
        self.btn_reset_view.setText("" if compact else "Reset View")
        self.panel_toggle.setText("" if compact else "PANEL")
        self.subtitle.setVisible(not very_compact)


class CameraFeedPanel(QWidget):
    """Responsive strip containing only driver and road-camera previews."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # A 640x480 frame changes QLabel.sizeHint(). Keep the vision area a
        # bounded strip so live frames cannot consume the 3D workspace. Its
        # exact height remains user-adjustable through the workspace splitter.
        self.setMinimumHeight(240)
        self.setMaximumHeight(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        heading = QLabel("VISION INPUTS")
        heading.setObjectName("appSubtitle")
        self._cards = QBoxLayout(QBoxLayout.LeftToRight)
        self._cards.setSpacing(8)
        self.driver = CameraPreviewCard("DRIVER / EYES", "Driver camera", "eye")
        self.headlight = CameraPreviewCard("ROAD / PRIMARY", "Road camera", "road")
        self.headlight_secondary = CameraPreviewCard(
            "ROAD / SECONDARY", "Stereo camera", "road")
        self._cards.addWidget(self.driver, 1)
        self._cards.addWidget(self.headlight, 1)
        self._cards.addWidget(self.headlight_secondary, 1)
        self._cards.addStretch(1)
        layout.addWidget(heading)
        layout.addLayout(self._cards)
        self.headlight_secondary.hide()

    def configure_sources(self, driver: bool, road: bool, stereo: bool):
        """Show only previews relevant to the selected operating mode."""
        self.driver.setVisible(driver)
        self.headlight.setVisible(road)
        self.headlight_secondary.setVisible(road and stereo)

    def set_stereo_frames(self, primary: QImage, secondary: QImage):
        self.headlight.set_frame(primary)
        self.headlight_secondary.set_frame(secondary)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = (
            QBoxLayout.TopToBottom if self.width() < 500
            else QBoxLayout.LeftToRight
        )
        if self._cards.direction() != direction:
            self._cards.setDirection(direction)


class SceneWorkspace(QFrame):
    """Own the 3D scene plus windshield and telemetry overlays."""

    def __init__(self, scene: QWidget, overlay: QWidget, telemetry=None, parent=None):
        super().__init__(parent)
        self.setObjectName("workspaceFrame")
        self.scene = scene
        self.overlay = overlay
        self.telemetry = telemetry
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(scene)
        overlay.setParent(self)
        overlay.setToolTip("Live windshield intersection view")
        overlay.show()
        overlay.raise_()
        if telemetry is not None:
            telemetry.setParent(self)
            telemetry.setProperty("overlay", True)
            telemetry.show()
            telemetry.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Scale the overlay proportionally but with sensible bounds
        width = min(420, max(240, int(self.width() * 0.32)))
        height = int(width * 0.58)
        margin = 12
        self.overlay.setGeometry(margin, margin, width, height)
        self.overlay.raise_()
        if self.telemetry is not None:
            telemetry_width = min(390, max(280, int(self.width() * 0.30)))
            telemetry_height = min(
                max(220, self.telemetry.sizeHint().height()),
                max(220, self.height() - margin * 2),
            )
            self.telemetry.setGeometry(
                self.width() - telemetry_width - margin,
                margin,
                telemetry_width,
                telemetry_height,
            )
            self.telemetry.raise_()


class ConfigurationSidebar(QFrame):
    """Dedicated right-side configuration panel."""

    def __init__(self, controls: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("configurationSidebar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("CONFIGURATION")
        heading.setObjectName("appSubtitle")
        heading.setContentsMargins(12, 8, 12, 0)
        layout.addWidget(heading)
        layout.addWidget(OperationsSidebar._scroll_page([controls]))


class EqualWidthTabBar(QTabBar):
    """Tab bar that allocates the available width evenly to every tab."""

    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        if self.count() and self.width() > 0:
            size.setWidth(max(1, self.width() // self.count()))
        return size

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateGeometry()


class OperationsSidebar(QTabWidget):
    """Tabbed sidebar separating live operations from configuration."""

    def __init__(self, overview_widgets: list[QWidget], controls: QWidget, parent=None):
        super().__init__(parent)
        self.setTabBar(EqualWidthTabBar(self))
        self.setDocumentMode(True)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.ElideRight)
        self.setIconSize(ICON_SIZE)
        self.tabBar().setExpanding(True)
        self.tabBar().setDrawBase(False)
        self.addTab(
            self._scroll_page(overview_widgets), IconFactory.icon("operations"), "OPERATIONS")
        self.addTab(
            self._scroll_page([controls]), IconFactory.icon("controls"), "CONFIGURATION")

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
