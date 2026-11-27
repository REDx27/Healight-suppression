"""Saved ToF calibration may follow a USB port only after live identity proof."""

import copy
import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from glare_tracker.installation import CalibrationStore, fit_tof
from glare_tracker.widgets.driver_calibration import DriverCalibrationDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(app, tmp_path):
    samples = [{"reference_cm": distance, "raw_cm": [distance - 1.] * 20,
                "split": "fit" if index < 3 else "validation"}
               for index, distance in enumerate((30., 50., 70., 40., 60.))]
    saved = fit_tof(samples, "sensor-A", sensor_z_cm=.5, eye_offset_cm=-.3)
    saved.update(port="COM4", measurements=samples)
    store = CalibrationStore(tmp_path)
    store.save("tof", saved)
    result = DriverCalibrationDialog(0, store, skips={"camera": False, "tof": True})
    result.port.setEditText("COM9")
    yield result
    result.reject()


def worker(port="COM9", identity="sensor-A", *, running=True, valid=True, age_ns=10_000_000,
           uncertainty_ns=1_000_000):
    return SimpleNamespace(port=port, isRunning=lambda: running, stop=lambda: True,
                           latest={"device_id": identity, "valid": valid, "raw_cm": 49.,
                                   "observed_ns": time.monotonic_ns() - age_ns,
                                   "uncertainty_ns": uncertainty_ns})


def test_same_sensor_proof_rebinds_only_saved_port(dialog):
    original = dialog.saved_tof
    expected = copy.deepcopy(original)
    expected["port"] = "COM9"
    dialog.sensor_worker = worker()

    dialog.use_saved_tof.click()

    assert dialog.store.load("tof") == expected
    assert dialog.saved_tof == expected
    assert original["port"] == "COM4"  # Do not mutate the prior in-memory record.
    assert not dialog.skips["tof"]
    assert "sensor-A" in dialog.range_message.text()
    assert "COM9" in dialog.range_message.text()


def test_different_sensor_does_not_inherit_calibration(dialog):
    original = copy.deepcopy(dialog.saved_tof)
    before = (dialog.store.directory / "tof.json").read_bytes()
    dialog.sensor_worker = worker(identity="sensor-B")

    dialog.use_saved_tof.click()

    assert dialog.saved_tof == original
    assert (dialog.store.directory / "tof.json").read_bytes() == before
    assert dialog.skips["tof"]
    assert "sensor-B" in dialog.range_message.text()
    assert "sensor-A" in dialog.range_message.text()
    assert "new calibration" in dialog.range_message.text()


@pytest.mark.parametrize("evidence", [
    "disconnected", "stopped", "different-port", "invalid", "stale", "future",
    "uncertain", "missing-time", "empty-port", "same-port-without-proof",
])
def test_unproven_connection_preserves_saved_profile(dialog, evidence):
    original = copy.deepcopy(dialog.saved_tof)
    before = (dialog.store.directory / "tof.json").read_bytes()
    connected = worker()
    if evidence == "disconnected":
        connected = None
    elif evidence == "stopped":
        connected = worker(running=False)
    elif evidence == "different-port":
        connected = worker(port="COM4")
    elif evidence == "invalid":
        connected = worker(valid=False)
    elif evidence == "stale":
        connected = worker(age_ns=200_000_000)
    elif evidence == "future":
        connected = worker(age_ns=-1_000_000_000)
    elif evidence == "uncertain":
        connected = worker(uncertainty_ns=110_000_000)
    elif evidence == "missing-time":
        connected.latest.pop("observed_ns")
    elif evidence == "empty-port":
        dialog.port.setEditText("")
    elif evidence == "same-port-without-proof":
        dialog.port.setEditText("COM4")
        connected = None
    dialog.sensor_worker = connected

    dialog.use_saved_tof.click()

    assert dialog.saved_tof == original
    assert (dialog.store.directory / "tof.json").read_bytes() == before
    assert dialog.skips["tof"]
    assert "Connect / reconnect" in dialog.range_message.text()
    assert "preserved" in dialog.range_message.text()


def test_failed_port_save_does_not_activate_or_replace_profile(dialog, monkeypatch):
    original = copy.deepcopy(dialog.saved_tof)
    before = (dialog.store.directory / "tof.json").read_bytes()
    dialog.sensor_worker = worker()

    def disk_failure(*args):
        raise OSError("test disk failure")

    monkeypatch.setattr(dialog.store, "save", disk_failure)
    dialog.use_saved_tof.click()

    assert dialog.saved_tof == original
    assert (dialog.store.directory / "tof.json").read_bytes() == before
    assert dialog.skips["tof"]
    assert "Could not save" in dialog.range_message.text()


def test_same_port_reuse_checks_identity_without_rewriting_profile(dialog, monkeypatch):
    dialog.port.setEditText("COM4")
    dialog.sensor_worker = worker(port="COM4")
    before = (dialog.store.directory / "tof.json").read_bytes()

    def unexpected_save(*args):
        pytest.fail("An unchanged port should not rewrite the profile")

    monkeypatch.setattr(dialog.store, "save", unexpected_save)
    dialog.use_saved_tof.click()

    assert not dialog.skips["tof"]
    assert (dialog.store.directory / "tof.json").read_bytes() == before


def test_camera_reuse_does_not_require_sensor_connection(dialog):
    dialog.skips["camera"] = True

    dialog._use_saved("camera")

    assert not dialog.skips["camera"]
    assert dialog.skips["tof"]
