"""Telemetry readout panel showing live coordinates and status."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QGroupBox, QFormLayout, QVBoxLayout, QLabel, QSizePolicy


_READOUT_STYLE = (
    "color: {color}; background-color: #0b0d11; "
    "padding: 6px 10px; border-radius: 5px; border: 1px solid #2a2f38;"
    "font-family: 'Consolas', 'Cascadia Code', monospace;"
)
_DEFAULT_COLOR = "#34d399"


class ReadoutPanel(QGroupBox):
    """Monospace telemetry readout showing coordinates and tracking status."""

    def __init__(self, parent=None):
        super().__init__("Telemetry", parent)
        self.setProperty("section", "telemetry")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(7)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)

        mono = QFont("Consolas", 9)
        self._labels: dict[str, QLabel] = {}
        self._label_colors: dict[str, str] = {}

        for key, label_text in [
            ("eye_pos", "Eye Position"),
            ("light_pos", "Light Sources"),
            ("fps", "Frame Rate"),
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
        self._intersection_box = QGroupBox("Intersections")
        self._intersection_box.setProperty("section", "results")
        self._intersection_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._intersection_layout = QVBoxLayout(self._intersection_box)
        self._intersection_layout.setContentsMargins(8, 12, 8, 8)
        self._intersection_layout.setSpacing(4)
        self._intersection_labels: list[QLabel] = []
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

        *intersections* is a list of ``(point_or_none, in_bounds)`` tuples.
        """
        self._intersection_placeholder.setVisible(not intersections)
        self._ensure_intersection_labels(len(intersections))

        for idx, (point, in_bounds) in enumerate(intersections, start=1):
            if point is None:
                text = f"#{idx}: No intersection"
                color = "#f87171"
            elif not in_bounds:
                ix, _, iz = point
                text = f"#{idx}: OUT  X:{ix:+6.1f}  Z:{iz:+6.1f}"
                color = "#f87171"
            else:
                ix, _, iz = point
                text = f"#{idx}: HIT  X:{ix:+6.1f}  Z:{iz:+6.1f}"
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
