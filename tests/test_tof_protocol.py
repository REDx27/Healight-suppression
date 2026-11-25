"""Controller-independent quality/timing checks; these are not hardware tests."""

import json
import time

import pytest

from glare_tracker.tof import RangeProtocol, eligible_range


def synchronized():
    protocol = RangeProtocol("run-1")
    now = 10_000_000_000
    protocol.feed(json.dumps({"type": "HELLO", "version": 1, "device_id": "tof-1", "session": "run-1"}), now)
    request = protocol.sync_request(now)
    protocol.feed(json.dumps({**request, "ms": 1010}), now + 20_000_000)
    return protocol


def packet(**changes):
    return json.dumps({"type": "RANGE", "session": "run-1", "seq": 1, "ms": 1050,
                       "mm": 500, "valid": True, "status": 0, "timeout": False,
                       "budget_ms": 33, **changes})


def test_synchronized_range_has_capture_time_and_identity():
    sample = synchronized().feed(packet(), 10_055_000_000)
    assert sample["valid"] and sample["raw_cm"] == 50
    assert sample["observed_ns"] == 10_017_000_000
    assert sample["uncertainty_ns"] == 10_000_000


@pytest.mark.parametrize("changes", [{"status": 4}, {"timeout": True}, {"valid": False},
                                    {"mm": 8190}, {"mm": True}, {"mm": float("nan")},
                                    {"budget_ms": 200}, {"status": False}])
def test_invalid_quality_or_range_is_never_valid(changes):
    assert not synchronized().feed(packet(**changes), 10_055_000_000)["valid"]


def test_stale_unsynced_duplicate_reset_and_wrong_session_are_rejected():
    assert not synchronized().feed(packet(), 11_000_000_000)["valid"]
    p = synchronized()
    p.feed(packet(), 10_055_000_000)
    with pytest.raises(ValueError, match="Duplicate, old or reset"):
        p.feed(packet(seq=1, ms=1060), 10_060_000_000)
    with pytest.raises(ValueError, match="session"):
        p.feed(packet(session="old-run"), 10_065_000_000)
    with pytest.raises(ValueError, match="HELLO"):
        RangeProtocol("run-1").feed(packet(), 10_055_000_000)
    with pytest.raises(ValueError, match="JSON object"):
        p.feed("[]", 10_065_000_000)


def test_long_clock_roundtrip_does_not_enable_range():
    p = synchronized()
    message = p.sync_request(20_000_000_000)
    with pytest.raises(ValueError, match="uncertainty"):
        p.feed(json.dumps({**message, "ms": 11000}), 20_100_000_000)


@pytest.mark.parametrize("changes", [{"seq": True}, {"ms": 1050.5}, {"budget_ms": "33"}])
def test_clock_and_sequence_fields_cannot_be_coerced_from_other_types(changes):
    with pytest.raises(ValueError, match="must be integers"):
        synchronized().feed(packet(**changes), 10_055_000_000)


def test_fusion_requires_matching_device_freshness_skew_and_latest_quality(monkeypatch):
    monkeypatch.setattr(time, "monotonic_ns", lambda: 1_000_000_000)
    sample = {"valid": True, "device_id": "tof-1", "observed_ns": 970_000_000, "uncertainty_ns": 5_000_000}
    assert eligible_range([sample], 980_000_000, "tof-1") is sample
    assert eligible_range([sample], 980_000_000, "other") is None
    assert eligible_range([sample], 900_000_000, "tof-1") is None
    assert eligible_range([sample, {**sample, "valid": False}], 980_000_000, "tof-1") is None
    assert eligible_range([{**sample, "observed_ns": 800_000_000}], 980_000_000, "tof-1") is None
