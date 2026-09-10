"""Application entry point — creates QApplication, shows the window, runs the event loop."""

import sys

from PyQt5.QtWidgets import QApplication

from glare_tracker.window import MainWindow


def main():
    """Launch the GlareTracker desktop application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(MainWindow._application_icon())

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
