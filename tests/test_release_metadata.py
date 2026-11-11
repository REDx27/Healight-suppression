"""Release metadata and lightweight UI-resource optimization checks."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from glare_tracker import __app_name__, __version__
from glare_tracker.widgets.icons import IconFactory


def test_release_reports_version_1_3():
    assert __app_name__ == "GlareTracker"
    assert __version__ == "1.3.0"


def test_repeated_vector_icons_reuse_cached_rendering():
    application = QApplication.instance() or QApplication([])
    IconFactory._cached_pixmap.cache_clear()

    first = IconFactory.pixmap("lock", "#969a9f", 14)
    second = IconFactory.pixmap("lock", "#969a9f", 14)
    cache = IconFactory._cached_pixmap.cache_info()

    assert not first.isNull()
    assert not second.isNull()
    assert cache.misses == 1
    assert cache.hits == 1
    application.processEvents()
