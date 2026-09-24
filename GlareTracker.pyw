"""GlareTracker — silent launcher (no console window).

Double-click this file to launch GlareTracker.
Python associates .pyw files with pythonw.exe which runs without a console.
"""

import os
import sys

# Ensure the working directory is the project root regardless of
# where this file is launched from (e.g. a desktop shortcut).
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from glare_tracker.app import main

main()
