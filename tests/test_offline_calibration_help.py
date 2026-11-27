"""Camera-free checks that calibration help remains usable without a network."""

import base64
from html.parser import HTMLParser
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QImage, QTextDocument
from PyQt5.QtWidgets import QApplication

import glare_tracker.calibration_help as help_content
import glare_tracker.widgets.calibration_guide as guide_ui


class ResourceLinks(HTMLParser):
    """Distinguish automatically loaded resources from optional clicked links."""

    def __init__(self, html):
        super().__init__()
        self.images = []
        self.resources = []
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in {"img", "script", "iframe", "source", "video", "audio"}:
            self.resources.extend(attrs[key] for key in ("src", "poster") if attrs.get(key))
        if tag == "link" and attrs.get("href"):
            self.resources.append(attrs["href"])


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def external_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(guide_ui.QDesktopServices, "openUrl",
                        lambda url: calls.append(QUrl(url)) or True)
    return calls


@pytest.fixture
def dialog(app, external_calls):
    widget = guide_ui.CalibrationGuideDialog(
        "Offline guide test", help_content.ALL_GUIDE_SECTIONS)
    yield widget
    widget.close()
    app.processEvents()


@pytest.mark.parametrize("name", help_content.GUIDE_IMAGES)
def test_bundled_figures_exist_and_decode_without_network(name):
    path = help_content.ASSET_ROOT / name
    assert path.is_file(), f"Missing offline figure: {path}"
    image = QImage(str(path))
    assert not image.isNull(), f"Unreadable offline figure: {path}"
    assert image.width() > 0 and image.height() > 0


def test_guide_figures_use_local_uris_and_qt_loads_them(dialog):
    seen = set()
    for index, (_, html) in enumerate(help_content.ALL_GUIDE_SECTIONS):
        resources = ResourceLinks(html)
        assert all(QUrl(url).isLocalFile() for url in resources.resources)
        for source in resources.images:
            url = QUrl(source)
            path = Path(url.toLocalFile())
            assert path.parent == help_content.ASSET_ROOT
            seen.add(path.name)
            loaded = dialog.tabs.widget(index).document().resource(
                QTextDocument.ImageResource, url)
            assert loaded is not None and not loaded.isNull(), source
    assert seen == set(help_content.GUIDE_IMAGES)


def test_all_tabs_remain_readable_in_small_offline_window(dialog, app, external_calls):
    dialog.resize(768, 552)
    dialog.show()
    app.processEvents()
    assert dialog.width() <= 768
    assert dialog.height() <= 552
    assert dialog.tabs.count() == len(help_content.ALL_GUIDE_SECTIONS)
    for index, (label, _) in enumerate(help_content.ALL_GUIDE_SECTIONS):
        dialog.tabs.setCurrentIndex(index)
        app.processEvents()
        browser = dialog.tabs.currentWidget()
        assert dialog.tabs.tabText(index) == label
        assert browser.accessibleName() == f"{label} instructions"
        assert len(browser.toPlainText().strip()) > 100
        assert browser.viewport().width() > 300
        assert browser.horizontalScrollBar().maximum() == 0, label
        assert browser.verticalScrollBar().maximum() > 0, label
        browser.verticalScrollBar().setValue(browser.verticalScrollBar().maximum())
        assert browser.verticalScrollBar().value() == browser.verticalScrollBar().maximum()
    assert external_calls == [], "Opening help or changing tabs must not open websites"


def test_missing_file_check_includes_model_pdf_and_empty_resources(tmp_path):
    root = tmp_path / "assets" / "calibration"
    expected = [root / name for name in (
        *help_content.GUIDE_IMAGES, *help_content.GUIDE_SOURCE_FIGURES)]
    manual = root / "offline_manual.html"
    model = root.parent / "face_landmarker.task"
    board = tmp_path / "output" / "pdf" / "road_stereo_chessboard_A4_9x6_20mm.pdf"
    expected.extend((manual, model, board))
    assert set(guide_ui.missing_offline_files(root)) == {str(path) for path in expected}
    for path in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"present")
    assert guide_ui.missing_offline_files(root) == []
    model.unlink()
    board.unlink()
    empty_picture = root / help_content.GUIDE_IMAGES[0]
    empty_picture.write_bytes(b"")
    assert set(guide_ui.missing_offline_files(root)) == {
        str(model), str(board), str(empty_picture)}


def test_file_check_warns_with_specific_restore_paths(dialog, tmp_path, monkeypatch):
    root = tmp_path / "assets" / "calibration"
    monkeypatch.setattr(guide_ui, "ASSET_ROOT", root)
    warnings = []
    monkeypatch.setattr(guide_ui.QMessageBox, "warning",
                        lambda parent, title, message: warnings.append((title, message)))

    dialog.check_files.click()

    assert len(warnings) == 1
    title, message = warnings[0]
    assert "Offline files" in title
    assert "Restore" in message
    assert str(root / "offline_manual.html") in message
    assert str(root.parent / "face_landmarker.task") in message
    assert str(tmp_path / "output" / "pdf" / "road_stereo_chessboard_A4_9x6_20mm.pdf") in message


def test_manual_button_opens_only_the_local_html(dialog, external_calls, monkeypatch):
    warnings = []
    monkeypatch.setattr(guide_ui.QMessageBox, "warning",
                        lambda *args: warnings.append(args))

    dialog.manual.click()

    assert len(external_calls) == 1
    assert external_calls[0].isLocalFile()
    assert Path(external_calls[0].toLocalFile()) == help_content.ASSET_ROOT / "offline_manual.html"
    assert warnings == []


@pytest.mark.parametrize("exists_but_cannot_open", [False, True])
def test_missing_or_unopenable_manual_warns_without_web_fallback(
        dialog, tmp_path, monkeypatch, external_calls, exists_but_cannot_open):
    root = tmp_path / "assets" / "calibration"
    root.mkdir(parents=True)
    monkeypatch.setattr(guide_ui, "ASSET_ROOT", root)
    attempted = []
    monkeypatch.setattr(guide_ui.QDesktopServices, "openUrl",
                        lambda url: attempted.append(QUrl(url)) or False)
    if exists_but_cannot_open:
        (root / "offline_manual.html").write_text("<html>Local manual</html>", encoding="utf-8")
    warnings = []
    monkeypatch.setattr(guide_ui.QMessageBox, "warning",
                        lambda parent, title, message: warnings.append((title, message)))

    dialog.manual.click()

    assert len(warnings) == 1
    assert "Offline manual unavailable" in warnings[0][0]
    assert "offline_manual.html" in warnings[0][1]
    assert "in-app written instructions remain available" in warnings[0][1]
    assert len(attempted) == int(exists_but_cannot_open)
    assert all(url.isLocalFile() for url in attempted)
    assert external_calls == []


def test_printable_manual_embeds_all_pictures_and_has_no_remote_assets():
    manual = help_content.ASSET_ROOT / "offline_manual.html"
    html = manual.read_text(encoding="utf-8")
    resources = ResourceLinks(html)
    assert len(resources.images) >= len(help_content.GUIDE_IMAGES)
    assert all(source.startswith("data:image/png;base64,") for source in resources.images)
    assert all(QUrl(source).scheme() == "data" for source in resources.resources)
    assert help_content.IMAGE_WIDTH_TOKEN not in html
    for source in resources.images:
        image = QImage.fromData(base64.b64decode(source.split(",", 1)[1]))
        assert not image.isNull()
    assert "optional" in html.lower() and "internet" in html.lower()


def test_missing_picture_has_actionable_written_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(help_content, "ASSET_ROOT", tmp_path)

    html = help_content.guide_image("lost.png", "Example illustration")

    assert "Local picture missing: lost.png" in html
    assert "Use the written steps" in html
    assert "restore the complete app folder" in html
    assert ResourceLinks(html).resources == []
