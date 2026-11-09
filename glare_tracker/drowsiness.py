"""Experimental driver-drowsiness metrics derived from face landmarks.

This module intentionally contains no Qt or camera code.  It can therefore be
unit-tested independently and reused by the driver-camera worker without
coupling drowsiness state to the glare-intersection calculations.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from math import hypot
import time


@dataclass(frozen=True)
class DrowsinessSettings:
    """Operator-selectable thresholds for the experimental detector."""

    enabled: bool = False
    eye_openness_threshold: float = 0.21
    blink_duration_ms: int = 800
    perclos_threshold: float = 0.25
    perclos_window_s: float = 60.0
    yawn_openness_threshold: float = 0.35
    yawn_duration_ms: int = 1500

    def normalized(self) -> "DrowsinessSettings":
        return DrowsinessSettings(
            enabled=bool(self.enabled),
            eye_openness_threshold=min(
                0.60, max(0.05, float(self.eye_openness_threshold))),
            blink_duration_ms=min(
                5000, max(100, int(self.blink_duration_ms))),
            perclos_threshold=min(
                0.95, max(0.01, float(self.perclos_threshold))),
            perclos_window_s=min(
                300.0, max(5.0, float(self.perclos_window_s))),
            yawn_openness_threshold=min(
                1.50, max(0.05, float(self.yawn_openness_threshold))),
            yawn_duration_ms=min(
                10000, max(250, int(self.yawn_duration_ms))),
        )


@dataclass(frozen=True)
class DrowsinessMetrics:
    """One live observation plus the detector's rolling temporal state."""

    valid: bool
    state: str
    eye_openness: float | None = None
    eyes_closed: bool = False
    closure_duration_ms: int = 0
    blink_count: int = 0
    perclos: float = 0.0
    mouth_openness: float | None = None
    yawning: bool = False
    yawn_count: int = 0
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return asdict(self)


# MediaPipe Face Mesh landmark order.  Each six-point tuple follows the EAR
# convention: outer corner, upper outer, upper inner, inner corner, lower
# inner, lower outer.
_LEFT_EYE = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE = (362, 385, 387, 263, 373, 380)
_MOUTH = (61, 13, 291, 14)  # left, upper, right, lower


def _point(landmarks, index: int, width: int, height: int) -> tuple[float, float]:
    landmark = landmarks[index]
    return float(landmark.x) * width, float(landmark.y) * height


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def eye_aspect_ratio(landmarks, indices, width: int, height: int) -> float:
    """Return the scale-independent eye aspect ratio (EAR)."""

    p1, p2, p3, p4, p5, p6 = (
        _point(landmarks, index, width, height) for index in indices)
    horizontal = 2.0 * _distance(p1, p4)
    if horizontal <= 1e-9:
        return 0.0
    return (_distance(p2, p6) + _distance(p3, p5)) / horizontal


def mouth_aspect_ratio(landmarks, width: int, height: int) -> float:
    """Return vertical mouth opening divided by mouth width."""

    left, upper, right, lower = (
        _point(landmarks, index, width, height) for index in _MOUTH)
    horizontal = _distance(left, right)
    if horizontal <= 1e-9:
        return 0.0
    return _distance(upper, lower) / horizontal


class DrowsinessDetector:
    """Maintain blink, PERCLOS, and sustained-yawn state over time."""

    def __init__(self, settings: DrowsinessSettings | None = None):
        self.settings = (settings or DrowsinessSettings()).normalized()
        self.reset()

    def reset(self) -> None:
        self._eye_closed_since: float | None = None
        self._yawn_since: float | None = None
        self._current_yawn_counted = False
        self._blink_count = 0
        self._yawn_count = 0
        self._perclos_samples: deque[tuple[float, bool]] = deque()

    def update_settings(self, settings: DrowsinessSettings) -> None:
        normalized = settings.normalized()
        if normalized != self.settings:
            self.settings = normalized
            self.reset()

    def unavailable(self) -> DrowsinessMetrics:
        """Mark face data unavailable without treating it as closed eyes."""

        self._eye_closed_since = None
        self._yawn_since = None
        self._current_yawn_counted = False
        return DrowsinessMetrics(
            valid=False,
            state="face_unavailable" if self.settings.enabled else "disabled",
            blink_count=self._blink_count,
            perclos=self._perclos(),
            yawn_count=self._yawn_count,
        )

    def update(
        self,
        landmarks,
        width: int,
        height: int,
        timestamp_s: float | None = None,
    ) -> DrowsinessMetrics:
        """Process one valid face observation."""

        if not self.settings.enabled:
            return self.unavailable()

        now = time.monotonic() if timestamp_s is None else float(timestamp_s)
        left_ear = eye_aspect_ratio(landmarks, _LEFT_EYE, width, height)
        right_ear = eye_aspect_ratio(landmarks, _RIGHT_EYE, width, height)
        eye_openness = (left_ear + right_ear) / 2.0
        mouth_openness = mouth_aspect_ratio(landmarks, width, height)

        eyes_closed = eye_openness < self.settings.eye_openness_threshold
        closure_duration_ms = 0
        if eyes_closed:
            if self._eye_closed_since is None:
                self._eye_closed_since = now
            closure_duration_ms = max(
                0, round((now - self._eye_closed_since) * 1000.0))
        elif self._eye_closed_since is not None:
            duration_ms = (now - self._eye_closed_since) * 1000.0
            # Ignore sub-frame landmark jitter but count ordinary and long blinks.
            if duration_ms >= 80.0:
                self._blink_count += 1
            self._eye_closed_since = None

        mouth_open = mouth_openness >= self.settings.yawn_openness_threshold
        yawn_duration_ms = 0
        if mouth_open:
            if self._yawn_since is None:
                self._yawn_since = now
                self._current_yawn_counted = False
            yawn_duration_ms = max(0, round((now - self._yawn_since) * 1000.0))
        else:
            self._yawn_since = None
            self._current_yawn_counted = False

        yawning = yawn_duration_ms >= self.settings.yawn_duration_ms
        if yawning and not self._current_yawn_counted:
            self._yawn_count += 1
            self._current_yawn_counted = True

        self._perclos_samples.append((now, eyes_closed))
        cutoff = now - self.settings.perclos_window_s
        while self._perclos_samples and self._perclos_samples[0][0] < cutoff:
            self._perclos_samples.popleft()
        perclos = self._perclos()

        reasons = []
        if closure_duration_ms >= self.settings.blink_duration_ms:
            reasons.append("prolonged eye closure")
        if (self._perclos_ready(now)
                and perclos >= self.settings.perclos_threshold):
            reasons.append("high PERCLOS")
        if yawning:
            reasons.append("sustained yawn")

        return DrowsinessMetrics(
            valid=True,
            state="warning" if reasons else "normal",
            eye_openness=eye_openness,
            eyes_closed=eyes_closed,
            closure_duration_ms=closure_duration_ms,
            blink_count=self._blink_count,
            perclos=perclos,
            mouth_openness=mouth_openness,
            yawning=yawning,
            yawn_count=self._yawn_count,
            reasons=tuple(reasons),
        )

    def _perclos(self) -> float:
        if not self._perclos_samples:
            return 0.0
        closed = sum(1 for _, is_closed in self._perclos_samples if is_closed)
        return closed / len(self._perclos_samples)

    def _perclos_ready(self, now: float) -> bool:
        """Require a useful observation span before issuing a PERCLOS warning."""

        if len(self._perclos_samples) < 5:
            return False
        observed_s = now - self._perclos_samples[0][0]
        required_s = min(10.0, self.settings.perclos_window_s * 0.20)
        return observed_s >= required_s
