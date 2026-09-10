"""Telemetry readout panel showing live coordinates and status."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QGroupBox, QFormLayout, QVBoxLayout, QLabel


_READOUT_STYLE = (
    "color: {color}; background-color: #0d1117; "
    "padding: 4px 8px; border-radius: 3px; border: 1px solid #222;"
)
_DEFAULT_COLOR = "#4caf50"


class ReadoutPanel(QGroupBox):
    """Monospace telemetry readout showing coordinates and tracking status."""

    def __init__(self, parent=None):
        super().__init__("📊 Telemetry", parent)
        layout = QFormLayout(self)
        layout.setSpacing(6)

        mono = QFont("Consolas", 10)
        self._labels: dict[str, QLabel] = {}

        for key, label_text in [
            ("eye_pos", "Eye Position"),
            ("light_pos", "Light Sources"),
            ("fps", "Frame Rate"),
            ("status", "Tracking"),
        ]:
            lbl = QLabel("—")
            lbl.setFont(mono)
            lbl.setStyleSheet(_READOUT_STYLE.format(color=_DEFAULT_COLOR))
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addRow(f"{label_text}:", lbl)
            self._labels[key] = lbl

        # Dynamic intersection list
        self._intersection_box = QGroupBox("Windshield Intersections")
        self._intersection_layout = QVBoxLayout(self._intersection_box)
        self._intersection_labels: list[QLabel] = []
        layout.addRow(self._intersection_box)

    # ── public API ──────────────────────────────────────────────────

    def set_value(self, key: str, text: str, color: str | None = None):
        """Update a single readout field by *key*."""
        if key in self._labels:
            self._labels[key].setText(text)
            if color:
                self._labels[key].setStyleSheet(_READOUT_STYLE.format(color=color))

    def set_intersections(self, intersections):
        """Replace the intersection list.

        *intersections* is a list of ``(point_or_none, in_bounds)`` tuples.
        """
        # Clear existing labels
        while self._intersection_labels:
            label = self._intersection_labels.pop()
            self._intersection_layout.removeWidget(label)
            label.deleteLater()

        for idx, (point, in_bounds) in enumerate(intersections, start=1):
            if point is None:
                text = f"Intersection {idx}: No mathematical intersection"
                color = "#f44336"
            elif not in_bounds:
                ix, _, iz = point
                text = (
                    f"Intersection {idx}: Out of Range — No valid "
                    f"windshield intersection (X:{ix:7.1f} Z:{iz:7.1f})"
                )
                color = "#f44336"
            else:
                ix, _, iz = point
                text = f"Intersection {idx}: X:{ix:7.1f}  Z:{iz:7.1f}  YES"
                color = "#4caf50"

            label = QLabel(text)
            label.setFont(QFont("Consolas", 9))
            label.setStyleSheet(_READOUT_STYLE.format(color=color))
            self._intersection_layout.addWidget(label)
            self._intersection_labels.append(label)

        if not intersections:
            placeholder = QLabel("—")
            placeholder.setFont(QFont("Consolas", 9))
            self._intersection_layout.addWidget(placeholder)
            self._intersection_labels.append(placeholder)
