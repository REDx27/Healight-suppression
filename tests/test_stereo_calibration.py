"""Camera-free checks for chessboard fitting, profile guards and stereo bring-up."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication, QLabel

import glare_tracker.calibration as calibration
import glare_tracker.capture as capture_module
import glare_tracker.headlight_detector as detector
import glare_tracker.widgets.stereo_calibration as wizard
from glare_tracker.operating_modes import OperatingMode
from glare_tracker.capture import CameraDevice
from glare_tracker.widgets.controls import ControlsPanel


def stereo_result():
    matrix = np.array([[500., 0., 320.], [0., 500., 240.], [0., 0., 1.]])
    distortion = np.zeros((5, 1))
    rotation, translation = np.eye(3), np.array([[-10.], [0.], [0.]])
    r1, r2, p1, p2, q, _, _ = cv2.stereoRectify(
        matrix, distortion, matrix, distortion, (640, 480), rotation, translation,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    return calibration.StereoCalibrationResult(
        calibration.CalibrationResult(matrix, distortion, (640, 480)),
        calibration.CalibrationResult(matrix.copy(), distortion.copy(), (640, 480)),
        rotation, translation, np.zeros((3, 3)), np.zeros((3, 3)),
        r1, r2, p1, p2, q, rms_error=0.2, camera_indices=(1, 2))


def observation(x, y=240):
    return SimpleNamespace(center=(x, y), confidence=0.9, diameter_px=10.)


def test_verified_camera_open_falls_back_from_dead_backend(monkeypatch):
    class FakeCapture:
        def __init__(self, readable):
            self.readable = readable
            self.released = False

        def isOpened(self):
            return True

        def read(self):
            return self.readable, (
                np.zeros((10, 10, 3), np.uint8) if self.readable else None)

        def release(self):
            self.released = True

    dead, working = FakeCapture(False), FakeCapture(True)
    captures = iter((dead, working))
    monkeypatch.setattr(capture_module.cv2, "VideoCapture", lambda *args: next(captures))
    monkeypatch.setattr(capture_module.QThread, "msleep", lambda value: None)

    selected, backend = capture_module.open_video_capture(0, verify_frames=True)

    assert selected is working
    assert backend == "Media Foundation"
    assert dead.released


def test_ordered_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(calibration, "_calibration_dir", lambda: tmp_path)
    result = stereo_result()
    name = calibration.stereo_profile_name(1, 2)
    calibration.save_stereo_calibration(result, name)
    loaded = calibration.load_stereo_calibration(name)
    assert loaded.camera_indices == (1, 2)
    assert loaded.baseline_cm == pytest.approx(10.)
    assert calibration.stereo_profile_compatible(loaded, 1, 2, (640, 480))
    assert not calibration.stereo_profile_compatible(loaded, 2, 1, (640, 480))
    assert not calibration.stereo_profile_compatible(loaded, 1, 2, (320, 240))
    assert not calibration.stereo_profile_compatible(loaded, 1, 1, (640, 480))
    assert calibration.load_stereo_calibration(calibration.stereo_profile_name(2, 1)) is None


@pytest.mark.parametrize("fault", ["legacy", "nan", "reversed", "bad_fit"])
def test_invalid_profile_is_rejected(fault):
    result = stereo_result()
    if fault == "legacy":
        result.camera_indices = None
    elif fault == "nan":
        result.R1[0, 0] = np.nan
    elif fault == "reversed":
        result.P2[0, 3] *= -1
    else:
        result.rms_error = 2.
    assert not calibration.stereo_profile_compatible(result, 1, 2, (640, 480))


@pytest.mark.parametrize("square", [0, -1, float("nan"), float("inf")])
def test_invalid_square_size_is_rejected(square):
    with pytest.raises(ValueError, match="square size"):
        calibration.calibrate_stereo([], [], square_size_cm=square)


def test_unpaired_or_mixed_resolution_samples_are_rejected():
    frame = np.zeros((480, 640, 3), np.uint8)
    with pytest.raises(ValueError, match="same number"):
        calibration.calibrate_stereo([frame], [])
    with pytest.raises(ValueError, match="same resolution"):
        calibration.calibrate_stereo([frame], [frame[:240]])
    assert calibration.calibrate_stereo([], []) is None


def test_synthetic_chessboard_fit_recovers_baseline(monkeypatch):
    truth = stereo_result()
    objects = calibration._build_object_points((9, 6), 2.5)
    pairs, corners = [], {}
    for i in range(15):
        rotation = np.array([0.06 * (i % 5 - 2), 0.09 * (i // 5 - 1), 0.03 * (i - 7)])
        translation = np.array([-10. + i % 3 * 3, -7. + i % 4 * 2, 65. + i * 4])
        pair = []
        for side in range(2):
            frame = np.full((480, 640, 3), i * 2 + side, np.uint8)
            image_points, _ = cv2.projectPoints(
                objects, rotation, translation + np.array([-10. * side, 0., 0.]),
                truth.cam1.camera_matrix, truth.cam1.dist_coeffs)
            corners[i * 2 + side] = image_points.astype(np.float32)
            pair.append(frame)
        pairs.append(tuple(pair))
    detect = lambda frame, pattern: corners[int(frame[0, 0, 0])]
    monkeypatch.setattr(calibration, "detect_checkerboard", detect)
    monkeypatch.setattr(wizard, "detect_checkerboard", detect)
    result = calibration.calibrate_stereo([p[0] for p in pairs], [p[1] for p in pairs])
    assert result.baseline_cm == pytest.approx(10., abs=0.02)
    assert result.rms_error < 0.01
    report = wizard.calibration_quality(result, pairs, (9, 6))
    assert report["passed"]
    assert report["fit_rectified_row_p95_px"] < 0.01
    result.P2[0, 3] *= -1
    assert not wizard.calibration_quality(result, pairs, (9, 6))["passed"]


def test_staged_stereo_fit_uses_supplied_intrinsics(monkeypatch):
    truth = stereo_result()
    objects = calibration._build_object_points((9, 6), 2.5)
    pairs, corners = [], {}
    for i in range(12):
        rotation = np.array([0.04 * (i % 4 - 1), 0.07 * (i // 4 - 1), 0.02 * i])
        translation = np.array([-8. + i % 3 * 2, -6. + i % 4, 70. + i * 5])
        pair = []
        for side in range(2):
            frame = np.full((480, 640, 3), i * 2 + side, np.uint8)
            image_points, _ = cv2.projectPoints(
                objects, rotation, translation + np.array([-10. * side, 0., 0.]),
                truth.cam1.camera_matrix, truth.cam1.dist_coeffs)
            corners[i * 2 + side] = image_points.astype(np.float32)
            pair.append(frame)
        pairs.append(tuple(pair))
    monkeypatch.setattr(
        calibration, "detect_checkerboard",
        lambda frame, pattern: corners[int(frame[0, 0, 0])])
    result = calibration.calibrate_stereo_with_intrinsics(
        [pair[0] for pair in pairs], [pair[1] for pair in pairs],
        truth.cam1, truth.cam2)
    assert result.baseline_cm == pytest.approx(10., abs=0.02)
    assert np.array_equal(result.cam1.camera_matrix, truth.cam1.camera_matrix)
    assert np.array_equal(result.cam2.camera_matrix, truth.cam2.camera_matrix)


def test_startup_prompt_only_for_missing_or_incompatible_pair():
    from glare_tracker.window import stereo_calibration_prompt_needed
    devices = [CameraDevice(1, 640, 480, "fake"), CameraDevice(2, 640, 480, "fake")]
    assert stereo_calibration_prompt_needed(devices, 1, 2, None)
    assert not stereo_calibration_prompt_needed(devices, 1, 2, stereo_result())
    assert not stereo_calibration_prompt_needed(devices, 1, 1, None)
    assert not stereo_calibration_prompt_needed(devices, 1, 3, None)
    mismatched = [devices[0], CameraDevice(2, 1280, 720, "fake")]
    assert not stereo_calibration_prompt_needed(mismatched, 1, 2, stereo_result())


def test_calibrated_matching_and_rejection():
    left = SimpleNamespace(observations=[observation(332.5)])
    right = SimpleNamespace(observations=[observation(307.5)])
    args = ((480, 640, 3), 19.5)
    assert detector._match_stereo_candidates(left, right, None, *args) == []
    sources = detector._match_stereo_candidates(left, right, stereo_result(), *args)
    assert len(sources) == 1
    assert sources[0].position == pytest.approx((0., 200., 19.5))
    assert detector._match_stereo_candidates(right, left, stereo_result(), *args) == []
    right.observations = [observation(307.5, 245)]
    assert detector._match_stereo_candidates(left, right, stereo_result(), *args) == []


def test_rough_uncalibrated_matching_is_visual_only_and_relaxed():
    left = SimpleNamespace(observations=[observation(200, 100)])
    right = SimpleNamespace(observations=[observation(170, 112)])
    candidates = detector._match_uncalibrated_candidates(
        left, right, (240, 320, 3), 19.5)
    assert len(candidates) == 1
    assert candidates[0].position[1] == 120.0
    assert candidates[0].confidence <= 0.45
    right.observations = [observation(170, 239)]
    left.observations.append(observation(250, 20))
    assert detector._match_uncalibrated_candidates(
        left, right, (240, 320, 3), 19.5) == []


def test_rough_uncalibrated_matching_pairs_two_lights_automatically():
    left = SimpleNamespace(observations=[
        observation(75, 105),
        observation(245, 125),
    ])
    # Reverse confidence/detection order to ensure matching is geometric, not
    # dependent on the list order returned by either detector.
    right = SimpleNamespace(observations=[
        observation(230, 127),
        observation(62, 108),
    ])

    candidates = detector._match_uncalibrated_candidates(
        left, right, (240, 320, 3), 19.5)

    assert len(candidates) == 2
    assert candidates[0].image_center == pytest.approx((75, 105))
    assert candidates[0].secondary_image_center == pytest.approx((62, 108))
    assert candidates[1].image_center == pytest.approx((245, 125))
    assert candidates[1].secondary_image_center == pytest.approx((230, 127))


def test_rough_multi_light_matching_compensates_camera_vertical_offset():
    left = SimpleNamespace(observations=[
        observation(75, 45),
        observation(245, 70),
    ])
    right = SimpleNamespace(observations=[
        observation(230, 172),
        observation(62, 147),
    ])

    candidates = detector._match_uncalibrated_candidates(
        left, right, (240, 320, 3), 19.5)

    assert len(candidates) == 2
    assert candidates[0].secondary_image_center == pytest.approx((62, 147))
    assert candidates[1].secondary_image_center == pytest.approx((230, 172))


def test_calibrated_matching_triangulates_two_lights_automatically():
    left = SimpleNamespace(observations=[
        observation(282.5, 230),
        observation(372.5, 250),
    ])
    right = SimpleNamespace(observations=[
        observation(347.5, 250),
        observation(257.5, 230),
    ])

    candidates = detector._match_stereo_candidates(
        left, right, stereo_result(), (480, 640, 3), 19.5)

    assert len(candidates) == 2
    assert candidates[0].secondary_image_center == pytest.approx((257.5, 230))
    assert candidates[1].secondary_image_center == pytest.approx((347.5, 250))
    assert all(candidate.position[1] == pytest.approx(200.0)
               for candidate in candidates)


def test_color_bar_test_pattern_is_rejected_but_scene_is_not():
    bars = np.zeros((240, 320, 3), np.uint8)
    colors = [(255, 255, 0), (0, 255, 0), (255, 0, 255), (0, 0, 255)]
    for index, color in enumerate(colors):
        bars[:, index * 80:(index + 1) * 80] = color
    scene = np.tile(np.arange(320, dtype=np.uint8), (240, 1))
    scene = cv2.cvtColor(scene, cv2.COLOR_GRAY2BGR)
    assert detector._is_color_bar_test_pattern(bars)
    assert not detector._is_color_bar_test_pattern(scene)


def test_dialog_rejects_duplicate_poses_and_archives_profile(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(calibration, "_calibration_dir", lambda: tmp_path)
    notices = []
    monkeypatch.setattr(
        wizard.QMessageBox, "information",
        lambda *args: notices.append(args),
    )
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog.session_dir = tmp_path / "stereo_sessions" / "test"
    dialog.session_dir.mkdir(parents=True)
    frame = np.zeros((30, 40, 3), np.uint8)
    corners = np.zeros((54, 1, 2), np.float32)
    dialog._sample((frame, frame, corners, corners))
    dialog._sample((frame, frame, corners.copy(), corners.copy()))
    assert len(dialog.pairs) == 1
    assert not dialog.fit.isEnabled()
    for i in range(1, 15):
        dialog._sample((frame, frame, corners + i * 10, corners + i * 10))
    assert dialog.fit.isEnabled()
    assert len(list(dialog.session_dir.glob("*.png"))) == 30
    report = dict(passed=True, stereo_rms_px=0.2, fit_rectified_row_p95_px=0.1, baseline_cm=10.)
    dialog._fit_done(stereo_result(), report)
    assert "PASSED — NOT SAVED YET" in dialog.fit_status.text()
    dialog._save()
    assert "PROFILE SAVED" in dialog.fit_status.text()
    assert dialog.saved_path.is_file()
    assert (dialog.session_dir / "report.json").is_file()
    assert (dialog.session_dir / "accepted_calib.npz").is_file()
    assert notices and notices[0][1] == "Stereo calibration complete — profile saved"
    assert dialog.result() == dialog.Accepted
    dialog.close()


def test_calibration_dialog_opens_verified_printable_board(monkeypatch):
    app = QApplication.instance() or QApplication([])
    board = wizard.printable_chessboard_path()
    assert board.is_file()
    assert board.read_bytes().startswith(b"%PDF-")
    opened = []
    monkeypatch.setattr(
        wizard.QDesktopServices, "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    dialog = wizard.StereoCalibrationDialog(0, 2)
    dialog.columns.setValue(7)
    dialog.rows.setValue(5)
    dialog.square.setValue(3.0)

    dialog.print_board.click()

    assert len(opened) == 1
    assert os.path.normcase(os.path.normpath(opened[0])) == os.path.normcase(
        os.path.normpath(str(board)))
    assert dialog.pattern == (9, 6)
    assert dialog.square.value() == pytest.approx(2.0)
    assert "Actual size" in dialog.message.text()
    dialog.close()


def test_visual_calibration_guide_assets_and_dialog():
    app = QApplication.instance() or QApplication([])
    for name in wizard.GUIDE_ASSETS:
        asset = wizard.calibration_guide_asset_path(name)
        assert asset.is_file()
        assert asset.read_text(encoding="utf-8").lstrip().startswith("<svg")
    guide = wizard.CalibrationVisualGuideDialog()
    images = [guide.findChild(QLabel, f"guideImage{index}") for index in range(1, 5)]
    assert all(label is not None for label in images)
    assert all(label.pixmap() is not None and not label.pixmap().isNull()
               for label in images)
    guide.close()


def test_dialog_advances_left_right_stereo_and_archives_intrinsics(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(calibration, "_calibration_dir", lambda: tmp_path)
    notices = []
    monkeypatch.setattr(
        wizard.QMessageBox, "information",
        lambda *args: notices.append(args),
    )
    dialog = wizard.StereoCalibrationDialog(1, 2)
    dialog.session_dir = tmp_path / "stereo_sessions" / "staged"
    dialog.session_dir.mkdir(parents=True)
    individual = stereo_result().cam1
    dialog._single_fit_done(individual)
    assert dialog.stage == "right"
    assert (dialog.session_dir / "left_intrinsic_calib.npz").is_file()
    assert notices[-1][1] == "LEFT intrinsic calibration passed"
    dialog._single_fit_done(individual)
    assert dialog.stage == "stereo"
    assert (dialog.session_dir / "right_intrinsic_calib.npz").is_file()
    assert dialog.start.text() == "Start STEREO calibration"
    assert notices[-1][1] == "RIGHT intrinsic calibration passed"
    assert "Frame resolution MATCHED" in dialog.frame_comparison.text()
    dialog.close()


def test_failed_stereo_fit_names_reversed_order_and_row_error(tmp_path):
    app = QApplication.instance() or QApplication([])
    dialog = wizard.StereoCalibrationDialog(2, 1)
    dialog.session_dir = tmp_path
    result = stereo_result()
    result.P2[0, 3] = abs(result.P2[0, 3])
    report = {
        "passed": False,
        "stereo_rms_px": 0.3,
        "fit_rectified_row_p95_px": 2.2,
        "baseline_cm": 15.0,
        "max_rms_px": 1.5,
        "max_row_p95_px": 2.0,
    }

    dialog._fit_done(result, report)

    assert "row error above limit" in dialog.fit_status.text()
    assert "order appears reversed" in dialog.fit_status.text()
    assert not dialog.save.isEnabled()
    dialog.close()


def test_stereo_panel_hides_unrelated_controls():
    app = QApplication.instance() or QApplication([])
    panel = ControlsPanel()
    assert panel.combo_detection_setup.currentText() == "Stereo Cameras"
    assert panel.combo_detection_setup.isHidden()
    panel.combo_operating_mode.setCurrentText(OperatingMode.DRIVER_FIXED.value)
    panel.combo_detection_setup.setCurrentText("Stereo Cameras")
    assert not panel.btn_stereo_calibration.isHidden()
    assert panel.spin_single_depth.isHidden()
    assert panel.spin_camera_hfov.isHidden()
    assert panel.movement_group.isHidden()
    assert panel.light_group.isHidden()
    assert panel.spin_min_light_area.isHidden()
    assert not panel.btn_stable_stereo_preset.isHidden()
    panel.check_show_advanced_detection.setChecked(True)
    assert not panel.spin_min_light_area.isHidden()
    panel.combo_detection_setup.setCurrentText("Single Camera")
    assert panel.btn_stereo_calibration.isHidden()
    assert not panel.spin_single_depth.isHidden()
    panel.close()


def test_stereo_detection_presets_preserve_stable_and_balanced_choices():
    app = QApplication.instance() or QApplication([])
    panel = ControlsPanel()

    panel.load_stable_stereo_preset()
    stable = panel.get_light_detection_settings()
    assert stable.min_area_px == 656
    assert stable.blur_size == 9
    assert stable.morphology_iterations == 5
    assert stable.match_distance_px == 221

    panel.load_balanced_stereo_preset()
    balanced = panel.get_light_detection_settings()
    assert balanced.min_area_px == 60
    assert balanced.blur_size == 5
    assert balanced.morphology_iterations == 2
    assert balanced.match_distance_px == 110
    panel.close()


@pytest.mark.parametrize("profile_state", ["missing", "valid", "wrong_resolution"])
def test_runtime_previews_without_uncalibrated_depth(monkeypatch, profile_state):
    app = QApplication.instance() or QApplication([])
    profile = stereo_result() if profile_state != "missing" else None
    if profile_state == "wrong_resolution":
        profile.cam2.image_size = (320, 240)
    loaded_names = []
    def load(name):
        loaded_names.append(name)
        return profile
    monkeypatch.setattr(detector, "load_stereo_calibration", load)
    worker = detector.HeadlightDetectorThread(1, 2)
    class Capture:
        released = False
        def grab(self):
            return True
        def retrieve(self):
            return True, np.zeros((480, 640, 3), np.uint8)
        def release(self):
            self.released = True
    captures = [Capture(), Capture()]
    monkeypatch.setattr(detector, "open_video_capture", lambda index: (captures[index - 1], "fake"))
    monkeypatch.setattr(
        detector, "configure_road_stereo_capture",
        lambda cap: ((320, 240, 15.0) if cap is captures[0]
                     else (352, 240, 15.0)))
    monkeypatch.setattr(detector, "_apply_camera_controls", lambda *args: {})
    processed = iter([
        SimpleNamespace(observations=[observation(332.5)]),
        SimpleNamespace(observations=[observation(307.5)]),
        SimpleNamespace(observations=[observation(332.5)]),
        SimpleNamespace(observations=[observation(307.5)]),
    ])
    monkeypatch.setattr(detector, "process_bright_spots", lambda *args: next(processed))
    monkeypatch.setattr(detector, "_preview_frame", lambda frame, *args, **kwargs: frame)
    results, rough_results, diagnostics, previews = [], [], [], []
    worker.lights_detected.connect(results.append)
    worker.rough_lights_detected.connect(rough_results.append)
    worker.stereo_diagnostics.connect(diagnostics.append)
    def stop_after_preview(*images):
        previews.append(images)
        if len(previews) == 2:
            worker._running = False
    worker.stereo_frames_ready.connect(stop_after_preview)
    worker.run()
    assert loaded_names == ["stereo_1_2"]
    assert len(previews) == 2
    assert bool(results) == (profile_state == "valid")
    assert bool(rough_results) == (profile_state != "valid")
    assert ("previews only" in diagnostics[0]) == (profile_state != "valid")
    assert all(cap.released for cap in captures)


def test_runtime_rejects_actual_frame_size_mismatch(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(detector, "load_stereo_calibration", lambda name: None)
    worker = detector.HeadlightDetectorThread(0, 2)

    class Capture:
        def __init__(self, shape):
            self.frame = np.zeros(shape, np.uint8)
            self.released = False
        def grab(self):
            return True
        def retrieve(self):
            return True, self.frame.copy()
        def release(self):
            self.released = True

    captures = {
        0: Capture((480, 640, 3)),
        2: Capture((480, 704, 3)),
    }
    monkeypatch.setattr(
        detector, "open_video_capture", lambda index: (captures[index], "fake"))
    monkeypatch.setattr(
        detector, "configure_road_stereo_capture", lambda cap: (640, 480, 15.0))
    monkeypatch.setattr(detector, "_apply_camera_controls", lambda *args: {})
    statuses = []
    worker.camera_status.connect(
        lambda message, valid: statuses.append((message, valid)))

    worker.run()

    assert statuses and statuses[-1][1] is False
    assert "different frame sizes after streaming" in statuses[-1][0]
    assert all(capture.released for capture in captures.values())


def test_runtime_marks_color_bar_stream_invalid(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(detector, "load_stereo_calibration", lambda name: None)
    worker = detector.HeadlightDetectorThread(0, 2)
    scene = np.full((240, 320, 3), 35, np.uint8)
    bars = np.zeros_like(scene)
    for index, color in enumerate(
            ((255, 255, 0), (0, 255, 0), (255, 0, 255), (0, 0, 255))):
        bars[:, index * 80:(index + 1) * 80] = color

    class Capture:
        def __init__(self, frame):
            self.frame, self.released = frame, False
        def grab(self):
            return True
        def retrieve(self):
            return True, self.frame.copy()
        def release(self):
            self.released = True

    captures = {0: Capture(scene), 2: Capture(bars)}
    monkeypatch.setattr(
        detector, "open_video_capture", lambda index: (captures[index], "fake"))
    monkeypatch.setattr(
        detector, "configure_road_stereo_capture", lambda cap: (320, 240, 15.0))
    monkeypatch.setattr(detector, "_apply_camera_controls", lambda *args: {})
    statuses, previews, metric, rough = [], [], [], []
    worker.stereo_stream_status.connect(
        lambda stream, message, valid: statuses.append((stream, message, valid)))
    worker.lights_detected.connect(metric.append)
    worker.rough_lights_detected.connect(rough.append)
    def stop_after_preview(*images):
        previews.append(images)
        worker._running = False
    worker.stereo_frames_ready.connect(stop_after_preview)

    worker.run()

    assert any(stream == 2 and not valid for stream, _, valid in statuses)
    assert len(previews) == 1
    assert metric == [] and rough == []
    assert all(capture.released for capture in captures.values())


def test_calibration_capture_reports_missing_camera_and_releases_first(monkeypatch):
    app = QApplication.instance() or QApplication([])
    released, errors = [], []
    camera = SimpleNamespace(release=lambda: released.append(True))
    monkeypatch.setattr(wizard, "open_video_capture", lambda index: (
        (camera, "fake") if index == 1 else (None, "none")))
    monkeypatch.setattr(wizard, "configure_road_stereo_capture", lambda cap: None)
    worker = wizard.StereoBoardCapture((1, 2), (9, 6))
    worker.status.connect(errors.append)
    worker.run()
    assert released == [True]
    assert "Camera 2 unavailable" in errors[-1]


def test_calibration_button_wiring_and_busy_camera_guard(monkeypatch):
    import glare_tracker.window as window_module
    app = QApplication.instance() or QApplication([])
    opened, messages = [], []
    class Dialog:
        saved_path = None
        def __init__(self, primary, secondary, parent):
            opened.append((primary, secondary))
        def exec_(self):
            pass
        def deleteLater(self):
            pass
    monkeypatch.setattr(window_module, "StereoCalibrationDialog", Dialog)
    monkeypatch.setattr(window_module.QMessageBox, "information", lambda *args: messages.append(args))
    window = window_module.MainWindow()
    window.controls.combo_operating_mode.setCurrentText(OperatingMode.DRIVER_FIXED.value)
    window.controls.combo_detection_setup.setCurrentText("Stereo Cameras")
    window.controls.btn_stereo_calibration.click()
    assert opened == [(1, 2)]
    # A blocked camera backend must not be destroyed or reused by calibration.
    deleted = []
    busy = SimpleNamespace(stop=lambda: None, isRunning=lambda: True,
                           deleteLater=lambda: deleted.append(True))
    window.headlight_thread = busy
    assert not window._stop_headlight_detection()
    assert window.headlight_thread is busy
    assert not deleted
    window.controls.btn_stereo_calibration.click()
    assert len(messages) == 1
    assert len(opened) == 1
    window.headlight_thread = None
    window.close()


def test_locked_driver_camera_is_excluded_from_stereo_calibration(monkeypatch):
    import glare_tracker.window as window_module
    app = QApplication.instance() or QApplication([])
    opened, warnings = [], []

    class Dialog:
        saved_path = None
        def __init__(self, primary, secondary, parent):
            opened.append((primary, secondary))
        def exec_(self):
            pass
        def deleteLater(self):
            pass

    monkeypatch.setattr(window_module, "StereoCalibrationDialog", Dialog)
    monkeypatch.setattr(
        window_module.QMessageBox, "warning",
        lambda *args: warnings.append(args),
    )
    window = window_module.MainWindow()
    window.controls.combo_operating_mode.setCurrentText(
        OperatingMode.DRIVER_FIXED.value)
    window.controls.combo_detection_setup.setCurrentText("Stereo Cameras")
    window.controls.spin_headlight_camera.setValue(
        window.controls.spin_driver_camera.value())

    window.controls.btn_stereo_calibration.click()

    assert opened == []
    assert warnings and warnings[-1][1] == (
        "Driver camera cannot calibrate road stereo")
    window.close()
