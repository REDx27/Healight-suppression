"""Centralized visual design system for the GlareTracker desktop UI.

Provides a cohesive simulation-studio theme with elevated charcoal surfaces,
violet interaction accents, and restrained semantic state colors.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    """Immutable color tokens shared by widgets and the application stylesheet."""

    # ── Backgrounds ──
    canvas: str = "#0b0b0f"          # deepest neutral background
    surface: str = "#15151b"         # card / panel background
    surface_raised: str = "#21212a"  # inputs, elevated cards
    surface_hover: str = "#2a2a35"   # hover state
    surface_glow: str = "#241a31"    # restrained violet interaction layer

    # ── Borders ──
    border: str = "#2b2b35"          # default border
    border_strong: str = "#484554"   # focused / prominent border
    border_glow: str = "#7c3aed"     # prominent accent border

    # ── Text ──
    text: str = "#f4f4f5"            # primary text
    text_muted: str = "#a1a1aa"      # secondary text
    text_dim: str = "#666672"        # disabled / hint text

    # ── Accent spectrum ──
    accent: str = "#8b5cf6"          # primary violet interaction accent
    accent_bright: str = "#d8b4fe"   # bright variant
    accent_dim: str = "#62409a"      # dimmed variant

    # ── Semantic ──
    success: str = "#34d399"         # green
    success_bg: str = "#0d2e23"      # green surface
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
                stop:0 #17171d, stop:0.55 #191720, stop:1 #141419);
            border: 1px solid {p.border};
            border-top: 1px solid #5b367c;
            border-bottom: 1px solid #5b367c;
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
            background: #18181f;
            border: 1px solid {p.border};
            border-left: 2px solid #5b367c;
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
            color: #c4b5fd;
        }}
        QLabel#cameraViewport {{
            background: #07080b;
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
            background: #17171d;
            border: 1px solid {p.border};
            border-left: 2px solid #553675;
            border-radius: 8px;
            margin-top: 16px;
            padding: 16px 12px 12px 12px;
            font-weight: 700;
            font-size: 9pt;
            color: #c4b5d5;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            background: #17171d;
        }}
        QGroupBox[section="results"] {{
            background: #141419;
            border-color: #30303a;
            border-left: 2px solid #553675;
        }}
        QGroupBox[section="results"]::title {{
            background: #141419;
            color: #c4b5d5;
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
            background: #211c2d;
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
        QPushButton#headerAction {{
            min-height: 30px;
            background: #171a20;
            color: {p.text_muted};
        }}
        QPushButton#headerAction:hover {{
            background: {p.surface_hover};
        }}
        QPushButton#headerAction[role="calibrate"] {{
            color: #c8c7d0;
            border-color: #393741;
            background: #1b1b22;
        }}
        QPushButton#headerAction[role="calibrate"]:hover {{
            color: #ede9fe;
            border-color: #7650a1;
            background: #261d39;
        }}
        QPushButton#headerAction[role="reset"] {{
            color: #c8c7d0;
            border-color: #393741;
            background: #1b1b22;
        }}
        QPushButton#headerAction[role="reset"]:hover {{
            color: #ede9fe;
            border-color: #7650a1;
            background: #261d39;
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
            background: #211a30;
            border-color: {p.accent_dim};
        }}

        /* ── Tabs ── */
        QTabWidget::pane {{
            background: #0d0f13;
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
            background: #22192d;
            color: {p.accent_bright};
            border-color: #60417f;
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
            background: #07090d;
            border: 1px solid #343a44;
            border-radius: 10px;
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
