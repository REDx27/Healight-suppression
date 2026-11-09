"""Unit tests for experimental landmark-based driver monitoring."""

from types import SimpleNamespace

import pytest

from glare_tracker.drowsiness import DrowsinessDetector, DrowsinessSettings


def _landmarks(eye_ratio=0.30, mouth_ratio=0.10):
    points = [SimpleNamespace(x=0.5, y=0.5) for _ in range(478)]

    def set_eye(indices, left, right, center_y):
        outer, upper_outer, upper_inner, inner, lower_inner, lower_outer = indices
        quarter = (right - left) * 0.25
        half_gap = eye_ratio * (right - left) / 2.0
        coordinates = {
            outer: (left, center_y),
            upper_outer: (left + quarter, center_y - half_gap),
            upper_inner: (right - quarter, center_y - half_gap),
            inner: (right, center_y),
            lower_inner: (right - quarter, center_y + half_gap),
            lower_outer: (left + quarter, center_y + half_gap),
        }
        for index, (x, y) in coordinates.items():
            points[index] = SimpleNamespace(x=x, y=y)

    set_eye((33, 160, 158, 133, 153, 144), 0.25, 0.45, 0.40)
    set_eye((362, 385, 387, 263, 373, 380), 0.55, 0.75, 0.40)

    mouth_half_gap = mouth_ratio * 0.20 / 2.0
    points[61] = SimpleNamespace(x=0.40, y=0.65)
    points[291] = SimpleNamespace(x=0.60, y=0.65)
    points[13] = SimpleNamespace(x=0.50, y=0.65 - mouth_half_gap)
    points[14] = SimpleNamespace(x=0.50, y=0.65 + mouth_half_gap)
    return points


def _settings(**overrides):
    values = dict(
        enabled=True,
        eye_openness_threshold=0.21,
        blink_duration_ms=800,
        perclos_threshold=0.25,
        perclos_window_s=10.0,
        yawn_openness_threshold=0.35,
        yawn_duration_ms=1500,
    )
    values.update(overrides)
    return DrowsinessSettings(**values)


def test_open_eyes_and_closed_mouth_report_normal():
    detector = DrowsinessDetector(_settings())

    result = detector.update(_landmarks(), 100, 100, timestamp_s=1.0)

    assert result.valid
    assert result.state == "normal"
    assert result.eye_openness == pytest.approx(0.30)
    assert result.mouth_openness == pytest.approx(0.10)
    assert not result.eyes_closed


def test_long_eye_closure_warns_and_completed_closure_counts_as_blink():
    detector = DrowsinessDetector(_settings())
    closed = _landmarks(eye_ratio=0.10)

    detector.update(closed, 100, 100, timestamp_s=1.0)
    warning = detector.update(closed, 100, 100, timestamp_s=1.9)
    reopened = detector.update(_landmarks(), 100, 100, timestamp_s=2.0)

    assert warning.state == "warning"
    assert "prolonged eye closure" in warning.reasons
    assert warning.closure_duration_ms == 900
    assert reopened.blink_count == 1


def test_perclos_waits_for_warmup_then_warns():
    detector = DrowsinessDetector(_settings(perclos_threshold=0.40))
    open_face = _landmarks(eye_ratio=0.30)
    closed_face = _landmarks(eye_ratio=0.10)

    early = detector.update(closed_face, 100, 100, timestamp_s=0.0)
    assert early.state == "normal"

    detector.update(open_face, 100, 100, timestamp_s=0.5)
    detector.update(closed_face, 100, 100, timestamp_s=1.0)
    detector.update(open_face, 100, 100, timestamp_s=1.5)
    result = detector.update(closed_face, 100, 100, timestamp_s=2.0)

    assert result.perclos == pytest.approx(0.60)
    assert "high PERCLOS" in result.reasons


def test_sustained_open_mouth_counts_one_yawn():
    detector = DrowsinessDetector(_settings())
    open_mouth = _landmarks(mouth_ratio=0.50)

    detector.update(open_mouth, 100, 100, timestamp_s=1.0)
    result = detector.update(open_mouth, 100, 100, timestamp_s=2.6)
    repeated = detector.update(open_mouth, 100, 100, timestamp_s=3.0)

    assert result.yawning
    assert "sustained yawn" in result.reasons
    assert result.yawn_count == 1
    assert repeated.yawn_count == 1


def test_missing_face_is_not_counted_as_closed_eyes():
    detector = DrowsinessDetector(_settings())
    detector.update(_landmarks(eye_ratio=0.10), 100, 100, timestamp_s=1.0)

    result = detector.unavailable()

    assert not result.valid
    assert result.state == "face_unavailable"
    assert not result.eyes_closed
