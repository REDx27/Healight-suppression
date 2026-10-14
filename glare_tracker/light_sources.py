"""Generic tracked-light records shared by detection and geometry.

The geometry pipeline intentionally does not classify a source as a motorcycle,
car, streetlight, or anything else.  Every valid bright source has the same
small record and is processed independently against every tracked eye.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Iterable, Optional

import numpy as np


@dataclass(frozen=True)
class LightCandidate:
    """One frame's measured light before temporal identity is assigned."""

    position: tuple[float, float, float]
    image_center: tuple[float, float]
    diameter_px: float
    confidence: float
    timestamp: float
    secondary_image_center: Optional[tuple[float, float]] = None


@dataclass(frozen=True)
class TrackedLightSource:
    """A vehicle-agnostic light source consumed by the application.

    ``stable_id`` remains attached to the same moving bright point across
    frames. ``timestamp`` is the last frame where it was actually observed;
    it is deliberately not refreshed while a short dropout is being held.
    """

    stable_id: str
    position: tuple[float, float, float]
    timestamp: float
    confidence: float
    state: str
    image_center: tuple[float, float]
    diameter_px: float
    secondary_image_center: Optional[tuple[float, float]] = None


@dataclass
class _MutableTrack:
    track_number: int
    position: np.ndarray
    image_center: np.ndarray
    diameter_px: float
    confidence: float
    timestamp: float
    secondary_image_center: Optional[np.ndarray]
    hits: int = 1
    missing_frames: int = 0


class LightSourceTracker:
    """Assign stable IDs and smooth a variable number of light candidates."""

    def __init__(
        self,
        smoothing_alpha: float = 0.35,
        hold_frames: int = 4,
        match_distance_px: float = 80.0,
        max_sources: int = 4,
    ):
        self.smoothing_alpha = float(np.clip(smoothing_alpha, 0.01, 1.0))
        self.hold_frames = max(0, int(hold_frames))
        self.match_distance_px = max(1.0, float(match_distance_px))
        self.max_sources = max(1, int(max_sources))
        self._tracks: dict[int, _MutableTrack] = {}
        self._next_track_number = 1

    def configure(self, match_distance_px: float, max_sources: int):
        self.match_distance_px = max(1.0, float(match_distance_px))
        self.max_sources = max(1, int(max_sources))
        if len(self._tracks) > self.max_sources:
            keep = sorted(
                self._tracks.values(),
                key=lambda track: (track.missing_frames, -track.confidence),
            )[:self.max_sources]
            self._tracks = {track.track_number: track for track in keep}

    def clear(self):
        self._tracks.clear()

    def update(
        self,
        candidates: Iterable[LightCandidate],
    ) -> list[TrackedLightSource]:
        candidates = sorted(
            list(candidates), key=lambda candidate: candidate.confidence,
            reverse=True,
        )[:self.max_sources]
        unmatched_tracks = set(self._tracks)
        unmatched_candidates = set(range(len(candidates)))

        # Greedy nearest-neighbour matching is adequate for compact bright
        # points in the controlled scene and, importantly, makes identity
        # independent of contour brightness ordering.
        possible_matches = []
        for track_number, track in self._tracks.items():
            for candidate_index, candidate in enumerate(candidates):
                distance = float(np.linalg.norm(
                    track.image_center - np.asarray(candidate.image_center)
                ))
                if distance <= self.match_distance_px:
                    possible_matches.append(
                        (distance, track_number, candidate_index)
                    )

        for _, track_number, candidate_index in sorted(possible_matches):
            if (track_number not in unmatched_tracks
                    or candidate_index not in unmatched_candidates):
                continue
            self._update_track(
                self._tracks[track_number], candidates[candidate_index]
            )
            unmatched_tracks.remove(track_number)
            unmatched_candidates.remove(candidate_index)

        for track_number in unmatched_tracks:
            track = self._tracks[track_number]
            track.missing_frames += 1
            track.confidence *= 0.78

        for candidate_index in sorted(unmatched_candidates):
            candidate = candidates[candidate_index]
            if len(self._tracks) >= self.max_sources:
                replaceable = [
                    self._tracks[track_number]
                    for track_number in unmatched_tracks
                    if track_number in self._tracks
                ]
                if not replaceable:
                    break
                victim = max(
                    replaceable,
                    key=lambda track: (
                        track.missing_frames,
                        -track.confidence,
                    ),
                )
                # In single-source motorcycle/test mode, the best current
                # candidate must replace a source that vanished elsewhere in
                # the image immediately. Holding the stale reflection here
                # made a newly presented real lamp appear undetectable.
                if (self.max_sources != 1
                        and candidate.confidence < victim.confidence):
                    break
                del self._tracks[victim.track_number]
                unmatched_tracks.discard(victim.track_number)
            track_number = self._next_track_number
            self._next_track_number += 1
            self._tracks[track_number] = _MutableTrack(
                track_number=track_number,
                position=np.asarray(candidate.position, dtype=np.float64),
                image_center=np.asarray(
                    candidate.image_center, dtype=np.float64),
                diameter_px=float(candidate.diameter_px),
                confidence=float(np.clip(candidate.confidence, 0.0, 1.0)),
                timestamp=float(candidate.timestamp),
                secondary_image_center=(
                    None if candidate.secondary_image_center is None
                    else np.asarray(
                        candidate.secondary_image_center, dtype=np.float64)
                ),
            )

        expired = [
            track_number for track_number, track in self._tracks.items()
            if track.missing_frames > self.hold_frames
        ]
        for track_number in expired:
            del self._tracks[track_number]

        return [
            self._snapshot(track)
            for track in sorted(
                self._tracks.values(), key=lambda item: item.track_number
            )
        ]

    def _update_track(self, track: _MutableTrack, candidate: LightCandidate):
        alpha = self.smoothing_alpha
        track.position += alpha * (
            np.asarray(candidate.position, dtype=np.float64) - track.position
        )
        track.image_center += alpha * (
            np.asarray(candidate.image_center, dtype=np.float64)
            - track.image_center
        )
        track.diameter_px += alpha * (
            float(candidate.diameter_px) - track.diameter_px
        )
        track.confidence = float(np.clip(
            0.55 * track.confidence + 0.45 * candidate.confidence,
            0.0,
            1.0,
        ))
        track.timestamp = float(candidate.timestamp)
        if candidate.secondary_image_center is None:
            track.secondary_image_center = None
        elif track.secondary_image_center is None:
            track.secondary_image_center = np.asarray(
                candidate.secondary_image_center, dtype=np.float64)
        else:
            track.secondary_image_center += alpha * (
                np.asarray(candidate.secondary_image_center, dtype=np.float64)
                - track.secondary_image_center
            )
        track.hits += 1
        track.missing_frames = 0

    @staticmethod
    def _snapshot(track: _MutableTrack) -> TrackedLightSource:
        if track.missing_frames:
            state = "temporarily_lost"
        elif track.hits == 1:
            state = "new"
        else:
            state = "tracked"
        return TrackedLightSource(
            stable_id=f"L{track.track_number}",
            position=tuple(float(value) for value in track.position),
            timestamp=track.timestamp,
            confidence=float(track.confidence),
            state=state,
            image_center=tuple(float(value) for value in track.image_center),
            diameter_px=float(track.diameter_px),
            secondary_image_center=(
                None if track.secondary_image_center is None
                else tuple(
                    float(value) for value in track.secondary_image_center
                )
            ),
        )


def candidate_now(
    position: tuple[float, float, float],
    image_center: tuple[float, float],
    diameter_px: float,
    confidence: float,
    secondary_image_center: Optional[tuple[float, float]] = None,
) -> LightCandidate:
    """Convenience constructor using a wall-clock capture timestamp."""

    return LightCandidate(
        position=position,
        image_center=image_center,
        diameter_px=diameter_px,
        confidence=confidence,
        timestamp=time.time(),
        secondary_image_center=secondary_image_center,
    )
