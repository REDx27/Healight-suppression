"""Application entry point — creates QApplication, shows the window, runs the event loop."""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from glare_tracker import __app_name__, __version__
from glare_tracker.window import MainWindow


def main():
    """Launch the GlareTracker desktop application."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("GlareTracker Research")
    app.setStyle("Fusion")
    app.setWindowIcon(MainWindow._application_icon())

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
