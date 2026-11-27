"""Telemetry readout panel showing live coordinates and status."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFrame, QFormLayout, QVBoxLayout, QLabel, QSizePolicy, QScrollArea, QWidget


_READOUT_STYLE = (
    "color: {color}; background: transparent; padding: 1px 0; border: none;"
    "font-family: 'Consolas'; font-size: 11px;"
)
_DEFAULT_COLOR = "#34d399"


class ReadoutPanel(QFrame):
    """Monospace telemetry readout showing coordinates and tracking status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("telemetryPanel")
        self.setProperty("section", "telemetry")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        title = QLabel("TELEMETRY")
        title.setObjectName("editorRegionTitle")
        title.setFixedHeight(28)
        title.setContentsMargins(12, 0, 12, 0)
        outer.addWidget(title)
        content = QWidget()
        content.setObjectName("telemetryContent")
        layout = QFormLayout(content)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(6)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        layout.setFormAlignment(Qt.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        mono = QFont("Consolas", 9)
        self._labels: dict[str, QLabel] = {}
        self._label_colors: dict[str, str] = {}

        for key, label_text in [
            ("eye_pos", "Eye position"),
            ("light_pos", "Light sources"),
            ("drowsiness", "Drowsiness"),
            ("fps", "Frame rate"),
            ("status", "Tracking"),
        ]:
            lbl = QLabel("---")
            lbl.setFont(mono)
            lbl.setStyleSheet(_READOUT_STYLE.format(color=_DEFAULT_COLOR))
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            layout.addRow(f"{label_text}:", lbl)
            self._labels[key] = lbl
            self._label_colors[key] = _DEFAULT_COLOR

        # Dynamic intersection list
        self._intersection_box = QWidget()
        self._intersection_box.setObjectName("telemetryIntersections")
        self._intersection_box.setProperty("section", "results")
        self._intersection_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._intersection_layout = QVBoxLayout(self._intersection_box)
        self._intersection_layout.setContentsMargins(0, 8, 0, 0)
        self._intersection_layout.setSpacing(2)
        self._intersection_labels: list[QLabel] = []
        caption = QLabel("INTERSECTIONS")
        caption.setObjectName("propertyPageTitle")
        self._intersection_layout.addWidget(caption)
        self._intersection_placeholder = self._make_intersection_label(
            "---", "#3d5268")
        self._intersection_layout.addWidget(self._intersection_placeholder)
        layout.addRow(self._intersection_box)

    # ── public API ──────────────────────────────────────────────────

    def set_value(self, key: str, text: str, color: str | None = None):
        """Update a single readout field by *key*."""
        if key in self._labels:
            label = self._labels[key]
            if label.text() != text:
                label.setText(text)
            if color and self._label_colors.get(key) != color:
                label.setStyleSheet(_READOUT_STYLE.format(color=color))
                self._label_colors[key] = color

    def set_intersections(self, intersections):
        """Replace the intersection list.

        Entries may be ``(point_or_none, in_bounds)`` for compatibility or
        ``(label, point_or_none, in_bounds)`` for per-eye results.
        """
        self._intersection_placeholder.setVisible(not intersections)
        self._ensure_intersection_labels(len(intersections))

        for idx, entry in enumerate(intersections, start=1):
            if len(entry) == 3:
                entry_label, point, in_bounds = entry
            else:
                point, in_bounds = entry
                entry_label = f"#{idx}"
            if point is None:
                text = f"{entry_label}: No intersection"
                color = "#f87171"
            elif not in_bounds:
                ix, _, iz = point
                text = f"{entry_label}: OUT  X:{ix:+6.1f}  Z:{iz:+6.1f}"
                color = "#f87171"
            else:
                ix, _, iz = point
                text = f"{entry_label}: HIT  X:{ix:+6.1f}  Z:{iz:+6.1f}"
                color = "#34d399"

            label = self._intersection_labels[idx - 1]
            label.setVisible(True)
            if label.text() != text:
                label.setText(text)
            if label.property("telemetryColor") != color:
                label.setProperty("telemetryColor", color)
                label.setStyleSheet(_READOUT_STYLE.format(color=color))

        for label in self._intersection_labels[len(intersections):]:
            label.hide()

    def _ensure_intersection_labels(self, count: int):
        """Grow the label pool without reallocating widgets every frame."""
        while len(self._intersection_labels) < count:
            label = self._make_intersection_label("", _DEFAULT_COLOR)
            self._intersection_layout.addWidget(label)
            self._intersection_labels.append(label)

    @staticmethod
    def _make_intersection_label(text: str, color: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Consolas", 8))
        label.setProperty("telemetryColor", color)
        label.setStyleSheet(_READOUT_STYLE.format(color=color))
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return label
