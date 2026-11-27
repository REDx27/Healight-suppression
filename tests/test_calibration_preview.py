"""Calibration presentation must preserve native pixels and physical camera roles."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtWidgets import QApplication

import glare_tracker.widgets.stereo_calibration as wizard
from glare_tracker.calibration import CalibrationResult


@pytest.fixture(scope="session")
def app():
    # Qt owns C++ wrappers globally. Keep this early-created application alive
    # through later camera-worker tests rather than deleting it between modules.
    return QApplication.instance() or QApplication([])


def image(color):
    result = QImage(640, 480, QImage.Format_RGB32)
    result.fill(QColor(color))
    return result


def test_late_left_signals_cannot_become_right_previews_or_samples(app, tmp_path, monkeypatch):
    monkeypatch.setattr(wizard, "_calibration_dir", lambda: tmp_path)
    monkeypatch.setattr(wizard.SingleBoardCapture, "start", lambda self: None)
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog._start()
    left_worker = dialog.capture_worker
    left_worker.preview.emit(image("red"))
    assert dialog.left.native_image.pixelColor(10, 10) == QColor("red")
    dialog.stage = "right"
    left_worker.preview.emit(image("blue"))
    assert dialog.right.native_image.isNull()
    dialog._start()
    left_worker.preview.emit(image("blue"))
    left_worker.sample.emit((np.zeros((480, 640, 3), np.uint8), np.zeros((54, 1, 2), np.float32)))
    assert not dialog.individual_frames["right"]
    dialog.capture_worker.preview.emit(image("green"))
    assert dialog.right.native_image.pixelColor(10, 10) == QColor("green")
    assert dialog.left.native_image.pixelColor(10, 10) == QColor("red")
    assert "MATCHED" in dialog.frame_comparison.text()
    dialog.close()


def test_equal_preview_canvases_fit_whole_frames_on_resize(app):
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog.resize(1000, 800)
    dialog.show()
    dialog._preview(image("red"), image("green"))
    app.processEvents()
    for width, height in ((1000, 800), (1200, 850), (900, 600)):
        dialog.resize(width, height)
        app.processEvents()
        assert abs(dialog.left.width() - dialog.right.width()) <= 1
        assert dialog.left.height() == dialog.right.height()
        for preview in (dialog.left, dialog.right):
            assert (preview.native_image.width(), preview.native_image.height()) == (640, 480)
            pixmap = preview.pixmap()
            assert abs(pixmap.width() / pixmap.height() - 4 / 3) < .02
        from PyQt5.QtCore import QPoint
        assert dialog.fit.mapTo(dialog, QPoint(0, 0)).y() + dialog.fit.height() <= dialog.height()
    dialog.close()


def test_raw_samples_are_not_resized_and_mode_changes_are_rejected(app, tmp_path):
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog.session_dir = tmp_path
    frame = np.full((480, 640, 3), 127, np.uint8)
    corners = np.arange(108, dtype=np.float32).reshape(54, 1, 2)
    dialog._sample_single((frame, corners))
    saved = cv2.imread(str(tmp_path / "left_001.png"))
    np.testing.assert_array_equal(saved, frame)
    dialog._sample_single((np.zeros((240, 320, 3), np.uint8), corners + 50))
    assert len(dialog.individual_frames["left"]) == 1
    assert "no resizing" in dialog.message.text()
    dialog.close()


def test_mismatched_right_intrinsics_never_advance_to_stereo(app):
    dialog = wizard.StereoCalibrationDialog(1, 2)
    matrix = np.array([[600., 0, 320], [0, 600, 240], [0, 0, 1]])
    dialog.intrinsics["left"] = CalibrationResult(matrix, np.zeros(5), (640, 480), .2)
    dialog.stage = "right"
    dialog._single_fit_done(CalibrationResult(matrix, np.zeros(5), (320, 240), .2))
    assert dialog.stage == "right" and dialog.intrinsics["right"] is None
    assert "native resolutions differ" in dialog.message.text()
    dialog.close()


def test_mismatch_caption_does_not_call_different_modes_normal(app):
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog._preview(image("red"), image("green").scaled(320, 240))
    assert "MISMATCHED" in dialog.frame_comparison.text()
    assert "normal" not in dialog.frame_comparison.text()
    corners = np.zeros((54, 1, 2), np.float32)
    dialog._sample((np.zeros((480, 640, 3), np.uint8), np.zeros((240, 320, 3), np.uint8), corners, corners))
    assert not dialog.pairs
    dialog.close()


def test_different_focal_lengths_at_same_resolution_stay_independent(app, tmp_path, monkeypatch):
    monkeypatch.setattr(wizard, "_calibration_dir", lambda: tmp_path)
    import glare_tracker.calibration as calibration
    monkeypatch.setattr(calibration, "_calibration_dir", lambda: tmp_path)
    monkeypatch.setattr(wizard.QMessageBox, "information", lambda *args: None)
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog._ensure_session()
    left = np.array([[858., 0, 320], [0, 858, 240], [0, 0, 1]])
    right = np.array([[897., 0, 320], [0, 897, 240], [0, 0, 1]])
    dialog._single_fit_done(CalibrationResult(left, np.zeros(5), (640, 480), .2))
    dialog._single_fit_done(CalibrationResult(right, np.zeros(5), (640, 480), .2))
    assert dialog.stage == "stereo"
    assert dialog.intrinsics["left"].focal_length_px == 858
    assert dialog.intrinsics["right"].focal_length_px == 897
    assert "MATCHED" in dialog.frame_comparison.text() and "Fitted fx differs" in dialog.frame_comparison.text()
    assert "4.5% relative to LEFT" in dialog.frame_comparison.text()
    dialog.close()


def test_failed_camera_open_can_retry_and_old_worker_cannot_disable_new_capture(app, tmp_path, monkeypatch):
    monkeypatch.setattr(wizard, "_calibration_dir", lambda: tmp_path)
    monkeypatch.setattr(wizard.SingleBoardCapture, "start", lambda self: None)
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog._start()
    old_worker = dialog.capture_worker
    old_worker.status.emit("Camera unavailable")
    old_worker.finished.emit()
    assert dialog.start.isEnabled() and not dialog.take.isEnabled()
    assert "Retry LEFT" in dialog.start.text()
    dialog._start()
    assert dialog.take.isEnabled()
    old_worker.status.emit("late failure from old camera")
    old_worker.finished.emit()
    assert dialog.take.isEnabled() and "late failure" not in dialog.message.text()
    dialog.close()


def test_fit_result_does_not_allow_close_before_thread_finished(app, monkeypatch):
    from PyQt5.QtCore import QThread
    dialog = wizard.StereoCalibrationDialog(1, 2)
    job = QThread(dialog)
    monkeypatch.setattr(job, "isRunning", lambda: True)
    dialog._fit_jobs.add(job)
    dialog.show()
    dialog._fit_failed("test failure before QThread.finished")
    assert dialog.fit_worker is None
    dialog.reject()
    assert dialog.isVisible() and "still fitting" in dialog.message.text()
    dialog._fit_jobs.clear()
    dialog.reject()
    assert not dialog.isVisible()


def test_archive_failure_keeps_intrinsic_stage_retryable(app, tmp_path, monkeypatch):
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog.session_dir = tmp_path
    def fail_archive(*args):
        raise OSError("disk full")
    monkeypatch.setattr(wizard, "save_single_calibration", fail_archive)
    matrix = np.array([[600., 0, 320], [0, 600, 240], [0, 0, 1]])
    dialog._single_fit_done(CalibrationResult(matrix, np.zeros(5), (640, 480), .2))
    assert dialog.stage == "left" and dialog.intrinsics["left"] is None
    assert dialog.start.isEnabled() and not dialog.save.isEnabled()
    assert "disk full" in dialog.message.text()
    dialog.close()


def test_rejected_stereo_fit_allows_more_pairs_and_refitting(app, tmp_path):
    from types import SimpleNamespace
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog.stage, dialog.session_dir = "stereo", tmp_path
    dialog.pairs = [None] * wizard.MIN_SAMPLES
    dialog.start.setEnabled(False)
    dialog.fit.setEnabled(False)
    result = SimpleNamespace(P2=np.array([[600., 0, 320, -9000], [0, 600, 240, 0], [0, 0, 1, 0]]))
    report = {"stereo_rms_px": .4, "fit_rectified_row_p95_px": 2., "baseline_cm": 15.,
              "max_rms_px": 1.5, "max_row_p95_px": 1.5, "passed": False}
    dialog._fit_done(result, report)
    assert dialog.start.isEnabled() and dialog.fit.isEnabled()
    assert not dialog.save.isEnabled() and "NOT ACCEPTED" in dialog.fit_status.text()
    dialog.close()
