"""Centralized visual design system for the GlareTracker desktop UI.

Provides a cohesive simulation-studio theme with elevated gray surfaces,
blue interaction accents, and restrained green semantic state colors.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    """Immutable color tokens shared by widgets and the application stylesheet."""

    # ── Backgrounds ──
    canvas: str = "#0b1117"          # deepest blue-gray background
    surface: str = "#121a22"         # card / panel background
    surface_raised: str = "#1b2732"  # inputs, elevated cards
    surface_hover: str = "#263746"   # hover state
    surface_glow: str = "#12324a"    # restrained blue interaction layer

    # ── Borders ──
    border: str = "#2c3a46"          # default border
    border_strong: str = "#536777"   # focused / prominent border
    border_glow: str = "#2f80ed"     # prominent accent border

    # ── Text ──
    text: str = "#f2f6f8"            # primary text
    text_muted: str = "#a8b6c1"      # secondary text
    text_dim: str = "#687987"        # disabled / hint text

    # ── Accent spectrum ──
    accent: str = "#2f80ed"          # primary blue interaction accent
    accent_bright: str = "#78b7ff"   # bright variant
    accent_dim: str = "#245d94"      # dimmed variant

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
            font-size: 10pt;
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
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #15212b, stop:0.55 #121b24, stop:1 #10171e);
            border: 1px solid {p.border};
            border-top: 1px solid #2f80ed;
            border-bottom: 1px solid #244a68;
            border-radius: 10px;
        }}
        QLabel#appTitle {{
            font-size: 18pt;
            font-weight: 800;
            color: {p.text};
            letter-spacing: 0.5px;
        }}
        QLabel#appSubtitle, QLabel#mutedText {{
            color: {p.text_muted};
            font-size: 8.5pt;
            letter-spacing: 1px;
        }}

        /* ── Camera Cards ── */
        QFrame#cameraCard {{
            background: #141e27;
            border: 1px solid {p.border};
            border-left: 2px solid #2f80ed;
            border-radius: 8px;
        }}
        QFrame#cameraCard:hover {{
            border-color: {p.border_strong};
        }}
        QLabel#cameraTitle {{
            font-weight: 700;
            font-size: 8.5pt;
            color: {p.text_muted};
            letter-spacing: 0.8px;
        }}
        QFrame#cameraCard QLabel#cameraTitle {{
            color: #9ccaff;
        }}
        QLabel#cameraViewport {{
            background: #080d12;
            border: 1px solid {p.border};
            border-radius: 6px;
            color: {p.text_dim};
            font-size: 9pt;
        }}

        /* ── Status Badges ── */
        QLabel#statusBadge {{
            border-radius: 10px;
            padding: 3px 10px;
            font-size: 7.5pt;
            font-weight: 800;
            letter-spacing: 0.5px;
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
            background: #141e27;
            border: 1px solid {p.border};
            border-left: 2px solid #2f80ed;
            border-radius: 8px;
            margin-top: 16px;
            padding: 16px 12px 12px 12px;
            font-weight: 700;
            font-size: 9pt;
            color: #b8c8d4;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            background: #141e27;
        }}
        QGroupBox[section="results"] {{
            background: #101820;
            border-color: #2c3a46;
            border-left: 2px solid #35b86b;
        }}
        QGroupBox[section="results"]::title {{
            background: #101820;
            color: #b8c8d4;
        }}
        QGroupBox[overlay="true"] {{
            background: rgba(14, 23, 31, 218);
            border: 1px solid rgba(91, 136, 168, 190);
            border-left: 2px solid #35b86b;
        }}
        QGroupBox[overlay="true"]::title {{
            background: rgba(14, 23, 31, 235);
        }}

        /* ── Inputs ── */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            min-height: 30px;
            background: {p.surface_raised};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 2px 10px;
            color: {p.text};
            selection-background-color: {p.accent_dim};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {p.accent};
            background: #172d3f;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 26px;
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
            min-height: 32px;
            background: {p.surface_raised};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 4px 14px;
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
            background: #080c12;
            border-color: #111a24;
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
            min-height: 30px;
            padding-left: 11px;
            padding-right: 11px;
            background: #15212b;
            border: 1px solid #354755;
            color: #b8c8d4;
            font-weight: 700;
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
            min-height: 30px;
            background: #18232d;
            color: {p.text_muted};
        }}
        QPushButton#headerAction:hover {{
            background: {p.surface_hover};
        }}
        QPushButton#headerAction[role="calibrate"] {{
            color: #c4d0d8;
            border-color: #344552;
            background: #18232d;
        }}
        QPushButton#headerAction[role="calibrate"]:hover {{
            color: #dceeff;
            border-color: #2f80ed;
            background: #173450;
        }}
        QPushButton#headerAction[role="reset"] {{
            color: #c4d0d8;
            border-color: #344552;
            background: #18232d;
        }}
        QPushButton#headerAction[role="reset"]:hover {{
            color: #dceeff;
            border-color: #2f80ed;
            background: #173450;
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
            background: #0e151c;
            border: 1px solid {p.border};
            border-top: none;
        }}
        QTabBar::tab {{
            background: {p.surface};
            color: {p.text_muted};
            border: 1px solid {p.border};
            padding: 11px 12px;
            min-width: 0;
            font-weight: 600;
            font-size: 8.5pt;
            letter-spacing: 0.8px;
        }}
        QTabBar::tab:first {{
            border-top-left-radius: 8px;
            border-bottom-left-radius: 8px;
        }}
        QTabBar::tab:last {{
            border-top-right-radius: 8px;
            border-bottom-right-radius: 8px;
        }}
        QTabBar::tab:selected {{
            background: #16314a;
            color: {p.accent_bright};
            border-color: #2f80ed;
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
            background: transparent;
            width: 6px;
            margin: 4px 1px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border_strong};
            border-radius: 3px;
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
            width: 3px;
        }}
        QSplitter::handle:vertical {{
            height: 3px;
        }}
        QSplitter::handle:hover {{
            background: {p.accent_dim};
        }}

        /* ── Workspace frame ── */
        QFrame#workspaceFrame {{
            background: #080e14;
            border: 1px solid #344756;
            border-radius: 10px;
        }}
        QFrame#configurationSidebar {{
            background: #0d151c;
            border: 1px solid #2b3d4a;
            border-radius: 8px;
        }}

        QToolButton#sceneToolButton {{
            min-width: 34px;
            max-width: 34px;
            min-height: 34px;
            max-height: 34px;
            padding: 0;
            background: rgba(20, 30, 39, 235);
            border: 1px solid #3b5366;
            border-radius: 7px;
        }}
        QToolButton#sceneToolButton:hover,
        QToolButton#sceneToolButton:checked {{
            background: #173f5f;
            border-color: #2f80ed;
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
