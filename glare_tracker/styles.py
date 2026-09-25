"""Centralized visual design system for the GlareTracker desktop UI.

Provides a cohesive dark theme with neon-accent graphics, glassmorphic
surfaces, and smooth UI polish.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    """Immutable color tokens shared by widgets and the application stylesheet."""

    # ── Backgrounds ──
    canvas: str = "#060a10"          # deepest background
    surface: str = "#0c1219"         # card / panel background
    surface_raised: str = "#111a24"  # inputs, elevated cards
    surface_hover: str = "#172231"   # hover state
    surface_glow: str = "#0d2a3d"    # subtle glow layer

    # ── Borders ──
    border: str = "#1a2736"          # default border
    border_strong: str = "#2a4460"   # focused / prominent border
    border_glow: str = "#0e7490"     # glowing accent border

    # ── Text ──
    text: str = "#e2eaf4"            # primary text
    text_muted: str = "#6b8299"      # secondary text
    text_dim: str = "#3d5268"        # disabled / hint text

    # ── Accent spectrum ──
    accent: str = "#22b8cf"          # primary cyan accent
    accent_bright: str = "#5ce0f0"   # bright variant
    accent_dim: str = "#0e7490"      # dimmed variant

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

        /* ── Header ── */
        QFrame#appHeader {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {p.surface}, stop:0.5 {p.surface_glow}, stop:1 {p.surface});
            border: 1px solid {p.border};
            border-bottom: 1px solid {p.border_glow};
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
            background: {p.surface};
            border: 1px solid {p.border};
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
        QLabel#cameraViewport {{
            background: #030508;
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
            background: {p.surface};
            border: 1px solid {p.border};
            border-radius: 8px;
            margin-top: 16px;
            padding: 16px 12px 12px 12px;
            font-weight: 700;
            font-size: 9pt;
            color: {p.accent};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
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
            background: {p.surface_glow};
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

        /* Primary action (Start Stream) */
        QPushButton#primaryAction {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #0c5c74, stop:1 #0a7e99);
            border: 1px solid {p.accent_dim};
            color: white;
            font-weight: 700;
            font-size: 10pt;
        }}
        QPushButton#primaryAction:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #0e7490, stop:1 #10a3b8);
            border-color: {p.accent};
        }}
        QPushButton#primaryAction:checked {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #7f1d1d, stop:1 #991b1b);
            border-color: {p.danger};
        }}
        QPushButton#sessionAction {{
            min-height: 30px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #0c5c74, stop:1 #0a7e99);
            border: 1px solid {p.accent_dim};
            color: white;
            font-weight: 700;
        }}
        QPushButton#sessionAction:hover {{
            border-color: {p.accent_bright};
            background: #0e7490;
        }}
        QPushButton#sessionAction:checked {{
            background: {p.danger_bg};
            border-color: {p.danger};
            color: #fecdd3;
        }}
        QPushButton#headerAction {{
            min-height: 30px;
            background: transparent;
            color: {p.text_muted};
        }}
        QPushButton#headerAction:hover {{
            color: {p.accent_bright};
            background: {p.surface_hover};
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
            background: {p.surface_glow};
            border-color: {p.accent_dim};
        }}

        /* ── Tabs ── */
        QTabWidget::pane {{
            background: {p.canvas};
            border: none;
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
            background: {p.surface_glow};
            color: {p.accent_bright};
            border-color: {p.accent_dim};
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
            background: {p.surface};
            border: 1px solid {p.border};
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
