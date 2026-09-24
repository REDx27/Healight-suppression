"""Centralized visual design system for the GlareTracker desktop UI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    """Immutable color tokens shared by widgets and the application stylesheet."""

    canvas: str = "#070b12"
    surface: str = "#0d1420"
    surface_raised: str = "#121c2a"
    surface_hover: str = "#182536"
    border: str = "#26364a"
    border_strong: str = "#35506d"
    text: str = "#e6edf6"
    text_muted: str = "#8fa2b7"
    accent: str = "#25b8e6"
    accent_hover: str = "#50c9ef"
    success: str = "#36d399"
    warning: str = "#f5b942"
    danger: str = "#ff647c"


class ThemeManager:
    """Build the Qt stylesheet from a single palette definition."""

    def __init__(self, palette: ThemePalette | None = None):
        self.palette = palette or ThemePalette()

    def stylesheet(self) -> str:
        p = self.palette
        return f"""
        QMainWindow, QWidget {{
            background-color: {p.canvas}; color: {p.text};
            font-family: "Segoe UI Variable", "Segoe UI", sans-serif; font-size: 10pt;
        }}
        QToolTip {{ color: {p.text}; background: {p.surface_raised}; border: 1px solid {p.border_strong}; padding: 5px; }}
        QFrame#appHeader, QFrame#cameraCard, QFrame#workspaceFrame {{
            background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px;
        }}
        QLabel#appTitle {{ font-size: 17pt; font-weight: 700; color: {p.text}; }}
        QLabel#appSubtitle, QLabel#mutedText {{ color: {p.text_muted}; font-size: 9pt; }}
        QLabel#cameraTitle {{ font-weight: 600; color: {p.text}; }}
        QLabel#cameraViewport {{
            background: #030609; border: 1px solid {p.border}; border-radius: 7px; color: {p.text_muted};
        }}
        QLabel#statusBadge {{
            border-radius: 8px; padding: 3px 9px; font-size: 8pt; font-weight: 700;
            background: {p.surface_raised}; color: {p.text_muted};
        }}
        QLabel#statusBadge[state="active"] {{ background: #12382f; color: {p.success}; }}
        QLabel#statusBadge[state="warning"] {{ background: #3b2d13; color: {p.warning}; }}
        QLabel#statusBadge[state="error"] {{ background: #3d1720; color: {p.danger}; }}
        QLabel#statusBadge[state="info"] {{ background: #12334a; color: {p.accent}; }}
        QGroupBox {{
            background: {p.surface}; border: 1px solid {p.border}; border-radius: 9px;
            margin-top: 14px; padding: 15px 10px 10px 10px; font-weight: 600; color: {p.accent};
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            min-height: 29px; background: {p.surface_raised}; border: 1px solid {p.border};
            border-radius: 6px; padding: 2px 8px; color: {p.text}; selection-background-color: {p.accent};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {p.accent}; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background: {p.surface_raised}; border: 1px solid {p.border_strong};
            selection-background-color: #174867; color: {p.text}; outline: 0;
        }}
        QPushButton, QToolButton {{
            min-height: 30px; background: {p.surface_raised}; border: 1px solid {p.border};
            border-radius: 6px; padding: 4px 12px; color: {p.text}; font-weight: 600;
        }}
        QPushButton:hover, QToolButton:hover {{ background: {p.surface_hover}; border-color: {p.accent}; }}
        QPushButton:pressed, QPushButton:checked {{ background: #123d55; border-color: {p.accent}; }}
        QPushButton:disabled {{ color: #536273; background: #0b111a; border-color: #192431; }}
        QPushButton#primaryAction {{ background: #0d6d8c; border-color: {p.accent}; color: white; }}
        QPushButton#primaryAction:hover {{ background: #1187aa; }}
        QPushButton#primaryAction:checked {{ background: #84283a; border-color: {p.danger}; }}
        QTabWidget::pane {{ background: {p.canvas}; border: none; }}
        QTabBar::tab {{
            background: {p.surface}; color: {p.text_muted}; border: 1px solid {p.border};
            padding: 9px 16px; min-width: 80px;
        }}
        QTabBar::tab:first {{ border-top-left-radius: 7px; border-bottom-left-radius: 7px; }}
        QTabBar::tab:last {{ border-top-right-radius: 7px; border-bottom-right-radius: 7px; }}
        QTabBar::tab:selected {{ background: #12334a; color: {p.accent}; border-color: {p.accent}; }}
        QScrollArea {{ border: none; background: transparent; }}
        QScrollBar:vertical {{ background: {p.canvas}; width: 8px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {p.border_strong}; border-radius: 4px; min-height: 30px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QSplitter::handle {{ background: {p.border}; }}
        QSplitter::handle:horizontal {{ width: 5px; }}
        QSplitter::handle:vertical {{ height: 5px; }}
        """


DEFAULT_THEME = ThemeManager()
DARK_STYLESHEET = DEFAULT_THEME.stylesheet()
