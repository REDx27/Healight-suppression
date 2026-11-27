"""Calibration must survive packaged-app restarts without touching source data."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import glare_tracker.calibration as calibration
from glare_tracker.installation import CalibrationStore


@pytest.fixture
def frozen_root(tmp_path, monkeypatch):
    monkeypatch.setattr(calibration.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user data"))
    monkeypatch.setattr(calibration.sys, "_MEIPASS", str(tmp_path / "extract_one"), raising=False)
    monkeypatch.setattr(calibration, "__file__", str(tmp_path / "extract_one" / "glare_tracker" / "calibration.py"))
    return tmp_path / "user data" / "GlareTracker" / "calibration"


def intrinsic():
    return calibration.CalibrationResult(
        np.array([[500., 0., 320.], [0., 500., 240.], [0., 0., 1.]]),
        np.zeros(5), (640, 480), .2)


def test_source_run_keeps_project_calibration_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(calibration.sys, "frozen", False, raising=False)
    monkeypatch.setattr(calibration, "__file__", str(tmp_path / "project" / "glare_tracker" / "calibration.py"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user data"))

    root = calibration._calibration_dir()

    assert root == tmp_path / "project" / "calibration"
    assert root.is_dir()
    assert not (tmp_path / "user data").exists()


def test_frozen_profiles_survive_a_different_extraction_directory(frozen_root, tmp_path, monkeypatch):
    model = intrinsic()
    projection = np.column_stack((model.camera_matrix, np.zeros(3)))
    projection_right = projection.copy()
    projection_right[0, 3] = -5000.
    stereo = calibration.StereoCalibrationResult(
        model, intrinsic(), np.eye(3), np.array([[-10.], [0.], [0.]]),
        np.zeros((3, 3)), np.zeros((3, 3)), np.eye(3), np.eye(3),
        projection, projection_right, np.eye(4), rms_error=.2, camera_indices=(1, 2))
    driver = calibration.DriverDepthCalibration(6.3, 55., 60., 523.8, (640, 480), 0)
    road = calibration.MonocularRangeCalibration(250., 18., 4500., (640, 480), 1, 215)
    saved_paths = [
        calibration.save_single_calibration(model, "driver_0"),
        calibration.save_stereo_calibration(stereo, "stereo_1_2"),
        calibration.save_driver_depth_calibration(driver),
        calibration.save_monocular_range_calibration(road),
    ]
    store = CalibrationStore()
    profiles = {"driver_0": {"camera_index": 0}, "tof": {"sensor_id": "test"},
                "rig": {"panel_size_cm": [44.28, 24.91]}}
    for name, payload in profiles.items():
        assert store.save(name, payload) == frozen_root / "installation" / f"{name}.json"
    assert all(path.parent == frozen_root and path.is_file() for path in saved_paths)

    # A one-file restart uses a new extraction folder; user calibration must not.
    monkeypatch.setattr(calibration.sys, "_MEIPASS", str(tmp_path / "extract_two"))
    monkeypatch.setattr(calibration, "__file__", str(tmp_path / "extract_two" / "glare_tracker" / "calibration.py"))
    monkeypatch.setattr(calibration.sys, "executable", str(tmp_path / "another install" / "GlareTracker.exe"))

    assert calibration._calibration_dir() == frozen_root
    np.testing.assert_array_equal(calibration.load_single_calibration("driver_0").camera_matrix,
                                  model.camera_matrix)
    loaded_stereo = calibration.load_stereo_calibration("stereo_1_2")
    assert loaded_stereo.camera_indices == (1, 2)
    assert loaded_stereo.baseline_cm == 10.
    assert calibration.load_driver_depth_calibration() == driver
    assert calibration.load_monocular_range_calibration() == road
    for name, payload in profiles.items():
        assert CalibrationStore().load(name) == payload
    assert not (tmp_path / "extract_one").exists()
    assert not (tmp_path / "extract_two").exists()


def test_frozen_sessions_share_the_persistent_profile_root(frozen_root):
    # Exercise both real session writers without opening cameras or Qt windows.
    from glare_tracker.widgets.driver_calibration import session_folder
    from glare_tracker.widgets.stereo_calibration import StereoCalibrationDialog

    for kind in ("driver", "tof", "rig"):
        folder = session_folder(kind)
        assert folder.parent == frozen_root / "installation_sessions"
        assert folder.is_dir()

    dialog = SimpleNamespace(session_dir=None, indices=(1, 2), pattern=(9, 6),
                             square=SimpleNamespace(value=lambda: 2.))
    assert StereoCalibrationDialog._ensure_session(dialog)
    assert dialog.session_dir.parent == frozen_root / "stereo_sessions"
    assert json.loads((dialog.session_dir / "setup.json").read_text())["camera_indices"] == [1, 2]
    original_session = dialog.session_dir
    assert StereoCalibrationDialog._ensure_session(dialog)
    assert dialog.session_dir == original_session
    archive = calibration.save_single_calibration(
        intrinsic(), f"stereo_sessions/{dialog.session_dir.name}/left_intrinsic")
    assert archive.parent == dialog.session_dir
    assert archive.is_file()


@pytest.mark.parametrize("local_app_data", [None, ""])
def test_frozen_missing_environment_uses_user_local_directory(tmp_path, monkeypatch, local_app_data):
    monkeypatch.setattr(calibration.sys, "frozen", True, raising=False)
    if local_app_data is None:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    else:
        monkeypatch.setenv("LOCALAPPDATA", local_app_data)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))

    assert calibration._calibration_dir() == tmp_path / "user" / "AppData" / "Local" / "GlareTracker" / "calibration"


def test_existing_user_and_legacy_files_are_never_migrated_or_overwritten(frozen_root, tmp_path):
    frozen_root.mkdir(parents=True)
    retained = frozen_root / "driver_0_calib.npz"
    retained.write_bytes(b"existing user profile")
    legacy = tmp_path / "extract_one" / "calibration"
    legacy.mkdir(parents=True)
    (legacy / retained.name).write_bytes(b"old bundled profile")

    assert calibration._calibration_dir() == frozen_root
    assert retained.read_bytes() == b"existing user profile"
    assert (legacy / retained.name).read_bytes() == b"old bundled profile"


def test_storage_errors_are_reported_without_switching_roots(frozen_root):
    frozen_root.parent.mkdir(parents=True)
    frozen_root.write_text("obstructed path", encoding="utf-8")

    with pytest.raises(OSError):
        calibration._calibration_dir()
    assert frozen_root.read_text(encoding="utf-8") == "obstructed path"


def test_explicit_calibration_store_directory_is_preserved(frozen_root, tmp_path):
    directory = tmp_path / "chosen backup"
    store = CalibrationStore(directory)

    path = store.save("rig", {"value": "explicit"})

    assert path == directory / "rig.json"
    assert store.load("rig") == {"value": "explicit"}
    assert not frozen_root.exists()
