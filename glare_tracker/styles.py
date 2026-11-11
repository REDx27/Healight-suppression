"""Centralized visual design system for the GlareTracker desktop UI.

Provides a cohesive simulation-studio theme with elevated gray surfaces,
blue interaction accents, and restrained green semantic state colors.
"""

from dataclasses import dataclass


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
    text: str = "#d8dadd"            # primary text
    text_muted: str = "#a9adb2"      # secondary text
    text_dim: str = "#6f747a"        # disabled / hint text

    # ── Accent spectrum ──
    accent: str = "#4779bd"          # primary blue interaction accent
    accent_bright: str = "#78a9e6"   # bright variant
    accent_dim: str = "#345d8d"      # dimmed variant

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
        return f"""
        /* ── Base ── */
        QMainWindow, QWidget {{
            background-color: {p.canvas};
            color: {p.text};
            font-family: "Segoe UI Variable", "Segoe UI", "Inter", sans-serif;
            font-size: 9pt;
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
            font-size: 13pt;
            font-weight: 700;
            color: {p.text};
            letter-spacing: 0.2px;
        }}
        QLabel#appSubtitle, QLabel#mutedText {{
            color: {p.text_muted};
            font-size: 8pt;
            letter-spacing: 0.25px;
        }}
        QLabel#propertyPageTitle {{
            color: #9da1a6;
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 0.7px;
            background: transparent;
            padding: 2px 4px 3px 4px;
            border: none;
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
            min-width: 34px;
            max-width: 34px;
            min-height: 34px;
            max-height: 34px;
            padding: 0;
            background: transparent;
            border: 1px solid transparent;
            border-left: 2px solid transparent;
            border-radius: 3px;
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
        QPushButton#propertyLinkButton {{
            min-height: 24px;
            padding: 1px 7px;
            color: #a9c9ed;
            background: #2d3e50;
            border-color: #3e6289;
        }}
        QPushButton#propertyLinkButton:hover {{
            color: #e3f0ff;
            background: #385572;
            border-color: #5c8fc8;
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
            font-weight: 700;
            font-size: 8.5pt;
            color: {p.text_muted};
            letter-spacing: 0.8px;
        }}
        QFrame#cameraCard QLabel#cameraTitle {{
            color: #9dc2ef;
        }}
        QLabel#cameraViewport {{
            background: #111214;
            border: none;
            border-radius: 0;
            color: {p.text_dim};
            font-size: 9pt;
        }}

        /* ── Status Badges ── */
        QLabel#statusBadge {{
            border-radius: 2px;
            padding: 2px 7px;
            font-size: 7pt;
            font-weight: 700;
            letter-spacing: 0.3px;
            background: {p.surface_raised};
            color: {p.text_dim};
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

        /* ── Group Boxes ── */
        QGroupBox {{
            background: #2b2d31;
            border: 1px solid #3b3e43;
            border-bottom-color: #191a1d;
            border-radius: 4px;
            margin-top: 18px;
            padding: 16px 8px 8px 8px;
            font-weight: 600;
            font-size: 8.5pt;
            color: #c8cbd0;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 8px;
            padding: 1px 6px;
            background: #2b2d31;
            border-radius: 2px;
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
        QGroupBox[overlay="true"] {{
            background: rgba(14, 23, 31, 218);
            border: 1px solid rgba(91, 136, 168, 190);
            border-left: 2px solid #35b86b;
        }}
        QGroupBox[overlay="true"]::title {{
            background: rgba(14, 23, 31, 235);
        }}
        QGroupBox[propertyPanel="true"] {{
            background: #303236;
            border: 1px solid #18191c;
            border-right-color: #3f4247;
            border-bottom-color: #121315;
            border-radius: 4px;
            margin: 0;
            padding: 0;
            font-weight: 400;
            color: #c8cbd0;
        }}
        QGroupBox[propertyPanel="true"]:disabled {{
            background: #292b2e;
            border-color: #1b1c1f;
            color: #777b80;
        }}

        /* ── Inputs ── */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            min-height: 26px;
            background: #3a3c41;
            border: 1px solid #202124;
            border-radius: 2px;
            padding: 1px 8px;
            color: {p.text};
            selection-background-color: {p.accent_dim};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {p.accent};
            background: #34383e;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 22px;
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
        QWidget#vectorEditor {{
            background: transparent;
        }}
        QLabel#vectorAxisLabel {{
            background: transparent;
            color: #c3c6ca;
            font-size: 8pt;
            font-weight: 400;
            padding: 0;
        }}
        QGroupBox[propertyPanel="true"] QLineEdit,
        QGroupBox[propertyPanel="true"] QSpinBox,
        QGroupBox[propertyPanel="true"] QDoubleSpinBox,
        QGroupBox[propertyPanel="true"] QComboBox {{
            min-height: 22px;
            background: #484a4e;
            border-color: #27282b;
            border-bottom-color: #202124;
            border-radius: 2px;
            padding-top: 0;
            padding-bottom: 0;
        }}
        QGroupBox[propertyPanel="true"] QLineEdit:hover,
        QGroupBox[propertyPanel="true"] QSpinBox:hover,
        QGroupBox[propertyPanel="true"] QDoubleSpinBox:hover,
        QGroupBox[propertyPanel="true"] QComboBox:hover {{
            background: #505256;
            border-color: #5b5e63;
        }}
        QToolButton#vectorLockButton,
        QToolButton#vectorResetButton {{
            min-width: 0;
            min-height: 0;
            padding: 0;
            background: transparent;
            border: 1px solid transparent;
            border-radius: 2px;
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
            font-size: 10pt;
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
            min-height: 27px;
            background: {p.surface_raised};
            border: 1px solid #18191b;
            border-radius: 3px;
            padding: 2px 10px;
            color: {p.text};
            font-weight: 600;
        }}
        QPushButton:hover, QToolButton:hover {{
            background: {p.surface_hover};
            border-color: {p.accent_dim};
            color: {p.accent_bright};
        }}
        QPushButton:pressed, QPushButton:checked {{
            background: {p.surface_glow};
            border-color: {p.accent};
        }}
        QPushButton:disabled {{
            color: {p.text_dim};
            background: #222428;
            border-color: #1c1d20;
        }}

        /* Primary action */
        QPushButton#primaryAction {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1d4ed8, stop:1 #2563eb);
            border: 1px solid #3b82f6;
            color: white;
            font-weight: 700;
            font-size: 10pt;
        }}
        QPushButton#primaryAction:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2563eb, stop:1 #3b82f6);
            border-color: #93c5fd;
        }}
        QPushButton#primaryAction:checked {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #7f1d1d, stop:1 #991b1b);
            border-color: {p.danger};
        }}
        QPushButton#sessionAction {{
            min-height: 30px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1d4ed8, stop:1 #2563eb);
            border: 1px solid #3b82f6;
            color: white;
            font-weight: 700;
        }}
        QPushButton#sessionAction:hover {{
            border-color: #93c5fd;
            background: #3171ed;
        }}
        QPushButton#sessionAction:checked {{
            background: {p.danger_bg};
            border-color: {p.danger};
            color: #fecdd3;
        }}
        QPushButton#sessionStateAction {{
            min-height: 27px;
            padding-left: 9px;
            padding-right: 9px;
            background: #33353a;
            border: 1px solid #17181a;
            color: #d0d2d5;
            font-weight: 600;
        }}
        QPushButton#sessionStateAction:hover {{
            border-color: #6da9d6;
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
            background: #7f1d1d;
            border-color: #f87171;
            color: #fee2e2;
        }}
        QPushButton#headerAction {{
            min-height: 27px;
            background: #33353a;
            color: {p.text_muted};
        }}
        QPushButton#headerAction:hover {{
            background: {p.surface_hover};
        }}
        QPushButton#headerAction[role="calibrate"] {{
            color: #c4d0d8;
            border-color: #18191b;
            background: #33353a;
        }}
        QPushButton#headerAction[role="calibrate"]:hover {{
            color: #dceeff;
            border-color: #4779bd;
            background: #384b60;
        }}
        QPushButton#headerAction[role="reset"] {{
            color: #c4d0d8;
            border-color: #18191b;
            background: #33353a;
        }}
        QPushButton#headerAction[role="reset"]:hover {{
            color: #dceeff;
            border-color: #4779bd;
            background: #384b60;
        }}
        QPushButton#simulationAction {{
            color: white;
            border-color: #3b82f6;
            background: #2563eb;
        }}
        QPushButton#simulationAction:hover {{
            color: white;
            border-color: #93c5fd;
            background: #3171ed;
        }}
        QPushButton#simulationAction:checked {{
            color: #fecdd3;
            border-color: {p.danger};
            background: {p.danger_bg};
        }}
        QToolButton#panelToggle {{
            min-height: 24px;
            padding: 2px 10px;
            color: {p.text_muted};
            font-size: 8pt;
            letter-spacing: 0.8px;
        }}
        QToolButton#panelToggle:checked {{
            color: {p.accent_bright};
            background: #173450;
            border-color: {p.accent_dim};
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
            font-size: 8pt;
            letter-spacing: 0.35px;
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
            min-width: 34px;
            max-width: 34px;
            min-height: 34px;
            max-height: 34px;
            padding: 0;
            background: rgba(20, 30, 39, 235);
            border: 1px solid #3b5366;
            border-radius: 3px;
        }}
        QToolButton#sceneToolButton:hover,
        QToolButton#sceneToolButton:checked {{
            background: #345574;
            border-color: #4779bd;
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
