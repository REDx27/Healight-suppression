"""Application entry point — creates QApplication, shows the window, runs the event loop."""

import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from glare_tracker import __app_name__, __version__
from glare_tracker.window import MainWindow


def main():
    """Launch the GlareTracker desktop application."""
    release_smoke_test = "--release-smoke-test" in sys.argv
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("GlareTracker Research")
    app.setStyle("Fusion")
    app.setWindowIcon(MainWindow._application_icon())

    window = MainWindow(discover_cameras=not release_smoke_test)
    window.show()

    if release_smoke_test:
        # Exercise imports, asset loading, OpenGL/Qt widget construction and a
        # clean shutdown without depending on the test machine's cameras.
        QTimer.singleShot(1500, window.close)
        QTimer.singleShot(2000, app.quit)

    sys.exit(app.exec_())
