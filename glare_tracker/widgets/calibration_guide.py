"""Plain-English help shared by the calibration entry point and dialogs."""

from PyQt5.QtCore import QRect, QSize, Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLayout, QTabWidget, QTextBrowser, QVBoxLayout, QLabel, QMessageBox

from glare_tracker.widgets.icons import command_button
from glare_tracker.calibration_help import ASSET_ROOT, IMAGE_WIDTH_TOKEN, GUIDE_IMAGES, GUIDE_SOURCE_FIGURES


def size_calibration_dialog(dialog: QDialog, width: int, height: int) -> None:
    screen = dialog.screen()
    if screen is not None:
        area = screen.availableGeometry()
        width = min(width, area.width() - 32)
        height = min(height, area.height() - 48)
    dialog.resize(width, height)


class CalibrationActions(QLayout):
    """Keep the same command order when a row wraps on a small screen."""

    def __init__(self, *buttons, stretch=True):
        super().__init__()
        self._items = []
        self._stretch = stretch
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)
        for button in buttons:
            self.addWidget(button)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < self.count() else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < self.count() else None

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def sizeHint(self):
        widths = sum(item.sizeHint().width() for item in self._items)
        return QSize(widths + self.spacing() * max(0, self.count() - 1),
                     self.minimumSize().height())

    def expandingDirections(self):
        return Qt.Horizontal

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def _arrange(self, rect, place):
        spacing = self.spacing()
        rows = []
        row = []
        used = 0
        for item in self._items:
            width = item.sizeHint().width()
            if row and used + spacing + width > rect.width():
                rows.append((row, used))
                row, used = [], 0
            used += width + (spacing if row else 0)
            row.append(item)
        if row:
            rows.append((row, used))

        y = rect.y()
        for row, used in rows:
            height = max(item.sizeHint().height() for item in row)
            if place:
                x = rect.x()
                spread = self._stretch and (len(row) > 1 or len(rows) == 1)
                extra = max(0, rect.width() - used) // len(row) if spread else 0
                for item in row:
                    width = item.sizeHint().width() + extra
                    item.setGeometry(QRect(x, y, width, height))
                    x += width + spacing
            y += height + spacing
        return max(0, y - rect.y() - spacing)


class OfflineGuideBrowser(QTextBrowser):
    """Keep local figures inside the viewport as the guide is resized."""

    def __init__(self, html, parent=None):
        super().__init__(parent)
        self._guide_html = html
        self._image_width = None
        self.setOpenExternalLinks(True)

    def render_guide(self):
        width = min(680, max(120, self.viewport().width() - 44))
        if self._image_width == width:
            return
        self._image_width = width
        position = self.verticalScrollBar().value()
        self.setHtml(self._guide_html.replace(IMAGE_WIDTH_TOKEN, str(width)))
        self.verticalScrollBar().setValue(position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render_guide()


def missing_offline_files(root=None):
    root = ASSET_ROOT if root is None else root
    required = [root / name for name in (*GUIDE_IMAGES, *GUIDE_SOURCE_FIGURES)]
    required.extend((root / "offline_manual.html",
                     root.parents[1] / "output" / "pdf" / "road_stereo_chessboard_A4_9x6_20mm.pdf",
                     root.parent / "face_landmarker.task"))
    return [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]


class CalibrationGuideDialog(QDialog):
    def __init__(self, title, sections, parent=None, *, current=0):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        self.offline_note = QLabel("Written steps and pictures work offline. Video links need internet and are optional.")
        self.offline_note.setWordWrap(True)
        self.offline_note.setObjectName("mutedText")
        layout.addWidget(self.offline_note)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        for label, html in sections:
            browser = OfflineGuideBrowser(html)
            browser.setObjectName("calibrationGuideText")
            browser.setAccessibleName(f"{label} instructions")
            browser.setOpenExternalLinks(True)
            document = browser.document()
            document.setDocumentMargin(18)
            document.setDefaultStyleSheet(
                "body { color: #d9dde3; font-family: 'Segoe UI'; font-size: 12px; } "
                "h2 { font-size: 18px; } h3 { font-size: 14px; color: #b6d6ff; } "
                "p, li { margin-bottom: 7px; } a { color: #9bc9ff; } "
                "pre { font-family: Consolas, monospace; color: #d0e4fd; }"
            )
            browser.render_guide()
            self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(current)
        layout.addWidget(self.tabs, 1)
        actions = QHBoxLayout()
        self.check_files = command_button("Check offline files", "fit")
        self.manual = command_button("Open complete offline manual", "folder")
        self.check_files.clicked.connect(self._check_files)
        self.manual.clicked.connect(self._open_manual)
        actions.addWidget(self.check_files)
        actions.addWidget(self.manual)
        actions.addStretch()
        close = command_button("Return to calibration", "back")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        size_calibration_dialog(self, 820, 680)

    def _check_files(self):
        missing = missing_offline_files()
        if missing:
            QMessageBox.warning(self, "Offline files need attention",
                "Restore the complete application folder before the trial. Missing or empty files:\n\n" + "\n".join(missing))
        else:
            QMessageBox.information(self, "Local guide files found",
                "Local pictures, manual, chessboard PDF and face model are present.\n\n"
                "This does not test cameras, USB drivers, firmware or physical accuracy. "
                "Follow the offline rehearsal before leaving the internet connection.")

    def _open_manual(self):
        manual = ASSET_ROOT / "offline_manual.html"
        if not manual.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(manual))):
            QMessageBox.warning(self, "Offline manual unavailable",
                "Restore assets/calibration/offline_manual.html from the complete app copy. "
                "The in-app written instructions remain available.")


from glare_tracker.calibration_help import (
    ROAD_STEPS, DRIVER_STEPS, TOF_STEPS, RIG_STEPS, LCD_STEPS, VERIFY_STEPS, overview_sections,
)
