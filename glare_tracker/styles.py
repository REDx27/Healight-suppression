"""Shared visual styles for the GlareTracker desktop controls."""

from dataclasses import dataclass
from pathlib import Path
import sys


_CONTROL_ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "assets" / "controls"

# Logical pixels scale with Qt's high-DPI support. Point-sized stylesheet
# fonts depend on the desktop's font DPI independently of our layout metrics.
CONTROL_HEIGHT = 24
PANEL_HEADER_HEIGHT = 28
PANEL_PADDING = 16
FORM_LABEL_WIDTH = 104
ROW_SPACING = 8


@dataclass(frozen=True)
class ThemePalette:
    """Immutable color tokens shared by widgets and the application stylesheet."""

    # ── Backgrounds ──
    canvas: str = "#1b1d20"          # 3D-editor shell
    surface: str = "#25272b"         # editor region
    surface_raised: str = "#303237"  # inputs and tool controls
    surface_hover: str = "#3a3d42"   # hover state
    surface_glow: str = "#294663"    # selected tool layer

    # ── Borders ──
    border: str = "#111214"          # editor-region divider
    border_strong: str = "#555a60"   # focused / prominent border
    border_glow: str = "#4b83c3"     # prominent accent border

    # ── Text ──
    text: str = "#d9dde3"            # primary text
    text_muted: str = "#a2aab5"      # secondary text
    text_dim: str = "#858d98"        # disabled text

    # ── Accent spectrum ──
    accent: str = "#4779bd"          # primary blue interaction accent
    accent_bright: str = "#78a9e6"   # bright variant
    accent_dim: str = "#345d8d"      # dimmed variant
    action: str = "#215eae"          # filled command button
    action_hover: str = "#2b6bc1"
    action_pressed: str = "#1b4d90"
    focus: str = "#abd4ff"           # keyboard focus ring

    # ── Semantic ──
    success: str = "#35c46f"         # green
    success_bg: str = "#103523"      # green surface
    warning: str = "#fbbf24"         # amber
    warning_bg: str = "#2d2510"      # amber surface
    danger: str = "#f87171"          # red
    danger_bg: str = "#2d1419"       # red surface
    info: str = "#60a5fa"            # blue
    info_bg: str = "#0f2440"         # blue surface


class ThemeManager:
    """Build the Qt stylesheet from a single palette definition."""

    def __init__(self, palette: ThemePalette | None = None):
        self.palette = palette or ThemePalette()

    def stylesheet(self) -> str:
        p = self.palette
        down = (_CONTROL_ASSETS / "chevron-down.svg").as_posix()
        up = (_CONTROL_ASSETS / "chevron-up.svg").as_posix()
        check = (_CONTROL_ASSETS / "check.svg").as_posix()
        return f"""
        /* ── Base ── */
        QMainWindow, QWidget {{
            background-color: {p.canvas};
            color: {p.text};
            font-family: "Segoe UI";
            font-size: 12px;
        }}

        QToolTip {{
            color: {p.text};
            background: {p.surface_raised};
            border: 1px solid {p.border_strong};
            border-radius: 4px;
            padding: 5px 8px;
        }}
        QLabel {{
            background: transparent;
        }}

        /* ── Header ── */
        QFrame#appHeader {{
            background: #2b2d31;
            border: none;
            border-bottom: 1px solid #0f1012;
            border-radius: 0;
        }}
        QLabel#appTitle {{
            font-size: 17px;
            font-weight: 600;
            color: {p.text};
        }}
        QLabel#appSubtitle, QLabel#mutedText {{
            color: {p.text_muted};
            font-size: 11px;
        }}
        QLabel#propertyPageTitle {{
            color: {p.text_muted};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1px;
            background: transparent;
            padding: 0;
            border: none;
        }}
        QLabel#editorRegionTitle {{
            background: #282a2e;
            color: {p.text_muted};
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1px;
            border: none;
            border-bottom: 1px solid #1b1d20;
        }}
        QFrame#telemetryPanel {{
            background: #25272b;
            border: none;
        }}
        QWidget#telemetryContent, QWidget#telemetryIntersections {{
            background: #25272b;
        }}
        QWidget#panelPresetRow, QWidget#cameraModeRow,
        QWidget#advancedShortcuts, QWidget#detectionAdvancedContainer,
        QWidget#lcdTestButtons {{
            background: transparent;
        }}
        QWidget#propertyEditor,
        QWidget#propertyPageContent,
        QStackedWidget#propertyPages {{
            background: #25272b;
        }}
        QWidget#propertyContextRail {{
            background: #202225;
            border-right: 1px solid #111214;
        }}
        QToolButton#propertyContextButton {{
            min-width: 0;
            min-height: 0;
            padding: 0;
            background: transparent;
            border: 1px solid transparent;
            border-left: 2px solid transparent;
            border-radius: 4px;
        }}
        QToolButton#propertyContextButton:hover {{
            background: #303338;
            border-color: #42464c;
        }}
        QToolButton#propertyContextButton:checked {{
            background: #34495f;
            border-color: #4779bd;
            border-left: 2px solid #78a9e6;
        }}
        /* ── Camera Cards ── */
        QFrame#cameraCard {{
            background: #25272b;
            border: 1px solid #111214;
            border-radius: 0;
        }}
        QFrame#cameraCard:hover {{
            border-color: #4b83c3;
        }}
        QLabel#cameraTitle {{
            font-weight: 600;
            font-size: 11px;
            color: {p.text_muted};
        }}
        QFrame#cameraCard QLabel#cameraTitle {{
            color: #9dc2ef;
        }}
        QLabel#cameraViewport {{
            background: #111214;
            border: none;
            border-radius: 0;
            color: {p.text_muted};
            font-size: 11px;
        }}

        /* ── Status Badges ── */
        QLabel#statusBadge {{
            border-radius: 4px;
            padding: 2px 5px;
            font-size: 10px;
            font-weight: 600;
            background: {p.surface_raised};
            color: {p.text_muted};
        }}
        QLabel#statusBadge[state="active"] {{
            background: {p.success_bg};
            color: {p.success};
        }}
        QLabel#statusBadge[state="warning"] {{
            background: {p.warning_bg};
            color: {p.warning};
        }}
        QLabel#statusBadge[state="error"] {{
            background: {p.danger_bg};
            color: {p.danger};
        }}
        QLabel#statusBadge[state="info"] {{
            background: {p.info_bg};
            color: {p.info};
        }}
        QLabel#statusBadge[state="idle"] {{
            background: transparent;
        }}

        /* ── Group Boxes ── */
        QGroupBox {{
            background: #2b2d31;
            border: 1px solid #3b3e43;
            border-bottom-color: #191a1d;
            border-radius: 4px;
            margin-top: 14px;
            padding: 12px 8px 8px 8px;
            font-weight: 600;
            font-size: 12px;
            color: {p.text};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 8px;
            padding: 1px 6px;
            background: #2b2d31;
            border-radius: 4px;
        }}
        QGroupBox[section="results"] {{
            background: #27292d;
            border-color: #373a3f;
            border-bottom-color: #18191b;
        }}
        QGroupBox[section="results"]::title {{
            background: #27292d;
            color: #b8bcc1;
        }}
        QGroupBox[section="telemetry"] QLabel {{
            font-size: 11px;
        }}
        QGroupBox[overlay="true"] {{
            background: rgba(14, 23, 31, 218);
            border: 1px solid rgba(91, 136, 168, 190);
            border-left: 2px solid #35b86b;
        }}
        QGroupBox[overlay="true"]::title {{
            background: rgba(14, 23, 31, 235);
        }}
        QGroupBox[propertyPanel="true"] {{
            background: #2c2e32;
            border: 1px solid #1c1e21;
            border-radius: 4px;
            margin: 0;
            padding: 0;
            font-weight: 400;
            color: #c8cdd4;
        }}
        QGroupBox[propertyPanel="true"]:disabled {{
            background: #292b2e;
            border-color: #1b1c1f;
            color: #777b80;
        }}

        /* ── Inputs ── */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            min-height: 18px;
            background: #3b3e43;
            border: 1px solid #484c53;
            border-radius: 3px;
            padding: 2px 7px;
            color: {p.text};
            selection-background-color: {p.accent_dim};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {p.focus};
            background: #34383e;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox {{
            padding-right: 26px;
        }}
        QComboBox::down-arrow {{
            image: url("{down}");
            width: 12px;
            height: 12px;
        }}
        QSpinBox, QDoubleSpinBox {{
            padding-right: 16px;
        }}
        QAbstractSpinBox QLineEdit {{
            min-height: 0;
            background: transparent;
            border: none;
            padding: 0;
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 14px;
            background: #303237;
            border: none;
            border-left: 1px solid #25262a;
            border-bottom: 1px solid #25262a;
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 14px;
            background: #303237;
            border: none;
            border-left: 1px solid #25262a;
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: url("{up}");
            width: 9px;
            height: 9px;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            image: url("{down}");
            width: 9px;
            height: 9px;
        }}
        QComboBox#cameraPreviewMode {{
            min-height: 16px;
            padding-top: 2px;
            padding-bottom: 2px;
            font-size: 11px;
        }}
        QCheckBox {{
            spacing: 7px;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid #89929e;
            border-radius: 3px;
            background: #292c30;
        }}
        QCheckBox::indicator:checked {{
            background: {p.action};
            image: url("{check}");
        }}
        QCheckBox::indicator:focus, QCheckBox::indicator:hover {{
            border-color: {p.focus};
        }}
        QCheckBox::indicator:disabled {{
            border-color: #4b5058;
            background: #222428;
        }}
        QWidget#vectorEditor {{
            background: transparent;
        }}
        QLabel#vectorAxisLabel {{
            background: transparent;
            color: #c3c6ca;
            font-size: 11px;
            font-weight: 400;
            padding: 0;
        }}
        QGroupBox[propertyPanel="true"] QLineEdit,
        QGroupBox[propertyPanel="true"] QSpinBox,
        QGroupBox[propertyPanel="true"] QDoubleSpinBox,
        QGroupBox[propertyPanel="true"] QComboBox {{
            min-height: 18px;
            background: #3b3e43;
        }}
        QGroupBox[propertyPanel="true"] QLineEdit:hover,
        QGroupBox[propertyPanel="true"] QSpinBox:hover,
        QGroupBox[propertyPanel="true"] QDoubleSpinBox:hover,
        QGroupBox[propertyPanel="true"] QComboBox:hover {{
            background: #43464c;
        }}
        QGroupBox[propertyPanel="true"] QLineEdit:focus,
        QGroupBox[propertyPanel="true"] QSpinBox:focus,
        QGroupBox[propertyPanel="true"] QDoubleSpinBox:focus,
        QGroupBox[propertyPanel="true"] QComboBox:focus {{
            border-color: {p.focus};
        }}
        QToolButton#vectorLockButton,
        QToolButton#vectorResetButton {{
            min-width: 0;
            min-height: 0;
            padding: 0;
            background: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            color: #a7aaae;
        }}
        QToolButton#vectorLockButton:hover,
        QToolButton#vectorResetButton:hover {{
            background: #44474c;
            border-color: #555960;
            color: #e0e2e5;
        }}
        QToolButton#vectorLockButton:checked {{
            background: #3b4652;
            border-color: #526a83;
        }}
        QToolButton#vectorResetButton {{
            font-size: 12px;
            color: #c6c9cd;
        }}
        QComboBox QAbstractItemView {{
            background: {p.surface_raised};
            border: 1px solid {p.border_strong};
            selection-background-color: {p.surface_glow};
            color: {p.text};
            outline: 0;
            padding: 4px;
        }}

        /* ── Buttons ── */
        QPushButton, QToolButton {{
            min-height: 18px;
            background: {p.surface_raised};
            border: 1px solid #494d54;
            border-radius: 3px;
            padding: 2px 8px;
            color: {p.text};
            font-weight: 400;
        }}
        QPushButton:hover:enabled, QToolButton:hover:enabled {{
            background: {p.surface_hover};
            border-color: #85909e;
        }}
        QPushButton:pressed, QPushButton:checked, QToolButton:pressed {{
            background: {p.surface_glow};
            border-color: {p.accent};
        }}
        QPushButton:disabled, QToolButton:disabled,
        QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
            color: {p.text_dim};
            background: #222428;
            border-color: #383a40;
        }}
        QPushButton[commandRole="guide"] {{
            color: #b9d2f1;
            background: #2e3b4c;
            border-color: #48617d;
        }}
        QPushButton[commandRole="guide"]:hover {{
            background: #34506e;
        }}
        QPushButton[commandRole="step"], QPushButton[commandRole="guide"] {{
            text-align: left;
        }}

        /* Primary commands and session states */
        QPushButton[commandRole="accent"]:enabled,
        QPushButton#sessionStateAction[sessionRole="run"]:!checked,
        QPushButton#simulationAction:!checked {{
            background: {p.action};
            border-color: #6b9cda;
            color: white;
        }}
        QPushButton[commandRole="accent"]:enabled:hover,
        QPushButton#sessionStateAction[sessionRole="run"]:!checked:hover,
        QPushButton#simulationAction:!checked:hover {{
            background: {p.action_hover};
        }}
        QPushButton[commandRole="accent"]:enabled:pressed,
        QPushButton#sessionStateAction[sessionRole="run"]:!checked:pressed,
        QPushButton#simulationAction:!checked:pressed {{
            background: {p.action_pressed};
        }}
        QPushButton#sessionStateAction[sessionRole="run"]:checked {{
            background: #166534;
            border-color: #4ade80;
            color: #dcfce7;
        }}
        QPushButton#sessionStateAction[sessionRole="standby"]:checked {{
            background: #854d0e;
            border-color: #facc15;
            color: #fef9c3;
        }}
        QPushButton#sessionStateAction[sessionRole="stop"]:checked {{
            background: #442d32;
            border-color: #805058;
            color: #edc3ca;
        }}
        QPushButton#simulationAction:checked {{
            color: #fecdd3;
            border-color: {p.danger};
            background: {p.danger_bg};
        }}
        QToolButton#panelToggle {{
            padding: 2px 8px;
        }}
        QToolButton#panelToggle:checked {{
            color: {p.accent_bright};
            background: #173450;
            border-color: {p.accent_dim};
        }}
        QPushButton:focus, QToolButton:focus,
        QPushButton[commandRole="guide"]:focus,
        QPushButton[commandRole="accent"]:focus:enabled,
        QPushButton#simulationAction:focus:checked,
        QPushButton#simulationAction:focus:!checked,
        QPushButton#sessionStateAction[sessionRole]:focus:checked,
        QPushButton#sessionStateAction[sessionRole]:focus:!checked,
        QToolButton#panelToggle:focus,
        QToolButton#propertyContextButton:focus,
        QToolButton#vectorLockButton:focus,
        QToolButton#vectorResetButton:focus {{
            border-color: {p.focus};
        }}

        /* ── Tabs ── */
        QTabWidget::pane {{
            background: #25272b;
            border: 1px solid {p.border};
            border-top: none;
        }}
        QTabBar::tab {{
            background: {p.surface};
            color: {p.text_muted};
            border: 1px solid {p.border};
            padding: 7px 10px;
            min-width: 0;
            font-weight: 600;
            font-size: 12px;
        }}
        QTabBar::tab:first {{
            border-radius: 0;
        }}
        QTabBar::tab:last {{
            border-radius: 0;
        }}
        QTabBar::tab:selected {{
            background: #344a62;
            color: {p.accent_bright};
            border-color: #4779bd;
            border-bottom: 2px solid {p.accent};
        }}
        QTabBar::tab:hover:!selected {{
            background: {p.surface_hover};
            color: {p.text};
        }}

        QLabel#calibrationTip {{
            color: #e2edfd;
            background: #27384d;
            border: 1px solid #546e8b;
            border-radius: 4px;
            padding: 8px 10px;
        }}
        QTextBrowser#calibrationGuideText {{
            background: {p.surface};
            border: 1px solid #454b54;
            border-radius: 4px;
            selection-background-color: {p.accent_dim};
            selection-color: white;
        }}

        /* ── Scroll ── */
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: #202226;
            width: 9px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border_strong};
            border-radius: 2px;
            min-height: 40px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.accent_dim};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        /* ── Splitters ── */
        QSplitter::handle {{
            background: {p.border};
        }}
        QSplitter::handle:horizontal {{
            width: 5px;
        }}
        QSplitter::handle:vertical {{
            height: 5px;
        }}
        QSplitter::handle:hover {{
            background: {p.accent_dim};
        }}

        /* ── Workspace frame ── */
        QFrame#workspaceFrame {{
            background: #080e14;
            border: none;
            border-radius: 0;
        }}
        QFrame#configurationSidebar {{
            background: #25272b;
            border: none;
            border-left: 1px solid #111214;
            border-radius: 0;
        }}

        QToolButton#sceneToolButton {{
            min-width: 0;
            min-height: 0;
            padding: 0;
            background: rgba(20, 30, 39, 235);
            border: 1px solid #3b5366;
            border-radius: 4px;
        }}
        QToolButton#sceneToolButton:hover,
        QToolButton#sceneToolButton:checked {{
            background: #345574;
            border-color: #4779bd;
        }}
        QToolButton#sceneToolButton:focus {{
            border-color: {p.focus};
        }}

        /* ── Slider ── */
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background: {p.border};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {p.accent};
            border: none;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {p.accent_bright};
        }}
        """


DEFAULT_THEME = ThemeManager()
DARK_STYLESHEET = DEFAULT_THEME.stylesheet()
