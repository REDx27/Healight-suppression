"""Live camera-feed display widget."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import QLabel


class VideoWidget(QLabel):
    """Displays camera frames with aspect-ratio preservation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #1a1a2e; border: 1px solid #333;")
        self._pixmap = None

        self.setText("📹  Camera Feed\nClick 'Start Stream' to begin")
        self.setFont(QFont("Segoe UI", 11))

    def update_frame(self, q_img: QImage):
        """Replace the displayed frame with *q_img*."""
        self._pixmap = QPixmap.fromImage(q_img)
        self.setText("")
        self._rescale()

    def clear_feed(self):
        """Remove the current frame and show placeholder text."""
        self._pixmap = None
        self.clear()
        self.setText("📹  Camera Feed\nStream stopped")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._pixmap:
            self.setPixmap(
                self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
