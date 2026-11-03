"""Regression coverage for generic multi-source light tracking and tuning."""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from glare_tracker.headlight_detector import (
    LightDetectionSettings,
    _preview_frame,
    detect_bright_spot_observations,
    process_bright_spots,
)
from glare_tracker.light_sources import (
    LightCandidate,
    LightSourceTracker,
    TrackedLightSource,
)
from glare_tracker.tracking import TrackingController


def _candidate(x, confidence=0.9, timestamp=1.0):
    return LightCandidate(
        position=(x, 150.0, 10.0),
        image_center=(x, 100.0),
        diameter_px=12.0,
        confidence=confidence,
        timestamp=timestamp,
    )


def test_detector_returns_independent_bright_sources():
    frame = np.full((240, 320, 3), 35, dtype=np.uint8)
    cv2.circle(frame, (75, 120), 10, (245, 245, 245), -1)
    cv2.circle(frame, (245, 105), 8, (230, 230, 230), -1)
    settings = LightDetectionSettings(
        brightness_threshold=190,
        adaptive_threshold=False,
        max_sources=4,
    )

    observations = detect_bright_spot_observations(frame, settings)

    assert len(observations) == 2
    centers = sorted(observation.center for observation in observations)
    assert centers[0][0] == pytest.approx(75.0, abs=2.0)
    assert centers[1][0] == pytest.approx(245.0, abs=2.0)
    assert all(0.0 <= observation.confidence <= 1.0
               for observation in observations)


def test_original_preview_is_the_unmodified_camera_frame():
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    frame[:, :, 1] = 73
    settings = LightDetectionSettings()
    processed = process_bright_spots(frame, settings)

    preview = _preview_frame(
        frame, processed, [], "Original", settings)

    assert np.array_equal(preview, frame)


def test_captured_background_rejects_static_window_but_keeps_new_light():
    background = np.full((240, 320, 3), 30, dtype=np.uint8)
    cv2.rectangle(background, (10, 10), (130, 225), (245, 245, 245), -1)
    current = background.copy()
    cv2.circle(current, (245, 120), 10, (255, 255, 255), -1)
    background_gray = cv2.cvtColor(background, cv2.COLOR_BGR2GRAY)
    settings = LightDetectionSettings(
        brightness_threshold=190,
        adaptive_threshold=False,
        background_rejection=True,
        background_difference_threshold=20,
        max_sources=4,
    )

    processed = process_bright_spots(
        current, settings, background_gray=background_gray)

    assert len(processed.observations) == 1
    center = processed.observations[0].center
    assert center[0] == pytest.approx(245.0, abs=2.0)
    assert center[1] == pytest.approx(120.0, abs=2.0)


def test_local_contrast_rejects_broad_window_but_keeps_phone_light():
    frame = np.full((240, 320, 3), 30, dtype=np.uint8)
    cv2.rectangle(frame, (10, 10), (130, 225), (245, 245, 245), -1)
    # The phone lamp is intentionally much dimmer than the window. This is
    # what auto exposure produces in the reported daylight test scene.
    cv2.circle(frame, (245, 120), 10, (145, 145, 145), -1)
    settings = LightDetectionSettings(
        brightness_threshold=190,
        adaptive_threshold=True,
        require_local_contrast=True,
        local_contrast_threshold=20,
        min_area_px=5,
        max_area_px=2000,
        blur_size=3,
        max_sources=4,
    )

    processed = process_bright_spots(frame, settings)

    assert len(processed.observations) == 1
    center = processed.observations[0].center
    assert center[0] == pytest.approx(245.0, abs=2.0)
    assert center[1] == pytest.approx(120.0, abs=2.0)


def test_multiscale_detector_selects_large_saturated_lamp_over_clutter():
    height, width = 480, 640
    gradient = np.linspace(65, 105, height, dtype=np.uint8)[:, None]
    frame = np.repeat(gradient, width, axis=1)
    frame = np.repeat(frame[:, :, None], 3, axis=2)

    # Broad illumination and long bright edges represent the wall/window and
    # furniture in the reported webcam scene. They are bright but not compact
    # peaks in every direction.
    cv2.rectangle(frame, (400, 280), (639, 479), (175, 175, 175), -1)
    cv2.line(frame, (20, 40), (350, 120), (205, 205, 205), 8)
    cv2.circle(frame, (430, 210), 8, (180, 180, 180), -1)

    # Model a nearby phone torch as a broad halo around a saturated core.
    yy, xx = np.indices((height, width))
    radius_squared = (xx - 245) ** 2 + (yy - 145) ** 2
    halo = 205.0 * np.exp(-radius_squared / (2.0 * 30.0 ** 2))
    for channel in range(3):
        frame[:, :, channel] = np.maximum(
            frame[:, :, channel], np.clip(55.0 + halo, 0, 255),
        ).astype(np.uint8)
    cv2.circle(frame, (245, 145), 13, (255, 255, 255), -1)

    settings = LightDetectionSettings(
        adaptive_threshold=True,
        brightness_threshold=210,
        min_area_px=5,
        max_area_px=50000,
        minimum_confidence=0.55,
        max_sources=4,
    )

    processed = process_bright_spots(frame, settings)

    assert processed.observations
    strongest = processed.observations[0]
    assert strongest.center[0] == pytest.approx(245.0, abs=8.0)
    assert strongest.center[1] == pytest.approx(145.0, abs=8.0)
    assert strongest.confidence >= settings.minimum_confidence


def test_coloured_light_uses_strongest_channel_instead_of_grayscale_loss():
    frame = np.full((240, 320, 3), 35, dtype=np.uint8)
    cv2.circle(frame, (170, 105), 9, (0, 0, 180), -1)
    settings = LightDetectionSettings(
        brightness_threshold=210,
        adaptive_threshold=True,
        max_sources=1,
    )

    processed = process_bright_spots(frame, settings)

    assert len(processed.observations) == 1
    assert processed.observations[0].center[0] == pytest.approx(170.0, abs=2.0)
    assert processed.observations[0].center[1] == pytest.approx(105.0, abs=2.0)


def test_saturated_core_is_fallback_when_saliency_floor_is_too_high():
    frame = np.full((240, 320, 3), 145, dtype=np.uint8)
    cv2.circle(frame, (95, 80), 18, (255, 255, 255), -1)
    settings = LightDetectionSettings(
        brightness_threshold=210,
        adaptive_threshold=True,
        require_local_contrast=True,
        local_contrast_threshold=250,
        minimum_confidence=0.25,
        max_sources=1,
    )

    processed = process_bright_spots(frame, settings)

    assert len(processed.observations) == 1
    assert processed.observations[0].detection_method == "peak core"
    assert processed.observations[0].center[0] == pytest.approx(95.0, abs=3.0)
    assert processed.observations[0].center[1] == pytest.approx(80.0, abs=3.0)


def test_peak_core_centroid_ignores_thin_connected_saturated_flare():
    frame = np.full((240, 320, 3), 80, dtype=np.uint8)
    cv2.circle(frame, (85, 105), 18, (255, 255, 255), -1)
    cv2.line(frame, (103, 105), (300, 105), (255, 255, 255), 2)
    settings = LightDetectionSettings(
        adaptive_threshold=True,
        local_contrast_threshold=250,
        minimum_confidence=0.25,
        max_sources=1,
    )

    processed = process_bright_spots(frame, settings)

    assert len(processed.observations) == 1
    source = processed.observations[0]
    assert source.detection_method == "peak core"
    assert source.center[0] == pytest.approx(85.0, abs=5.0)
    assert source.center[1] == pytest.approx(105.0, abs=3.0)


def test_white_peak_core_is_ranked_above_red_channel_skin_highlights():
    frame = np.full((300, 420, 3), (55, 75, 95), dtype=np.uint8)
    # Skin-like patches clip the red channel but remain much lower in blue and
    # green, matching the false white regions seen in the strongest-channel
    # diagnostic mask.
    cv2.circle(frame, (275, 205), 24, (85, 155, 255), -1)
    cv2.ellipse(frame, (315, 255), (12, 35), 0, 0, 360,
                (75, 145, 255), -1)
    cv2.circle(frame, (105, 85), 11, (255, 255, 255), -1)
    settings = LightDetectionSettings(
        adaptive_threshold=True,
        local_contrast_threshold=250,
        minimum_confidence=0.25,
        max_sources=1,
    )

    processed = process_bright_spots(frame, settings)

    assert len(processed.observations) == 1
    source = processed.observations[0]
    assert source.detection_method == "peak core"
    assert source.center[0] == pytest.approx(105.0, abs=3.0)
    assert source.center[1] == pytest.approx(85.0, abs=3.0)


def test_startup_defaults_choose_lamp_instead_of_nose_like_highlight():
    frame = np.full((300, 420, 3), (50, 70, 90), dtype=np.uint8)
    cv2.circle(frame, (210, 145), 10, (90, 165, 255), -1)
    cv2.circle(frame, (95, 75), 12, (255, 255, 255), -1)

    processed = process_bright_spots(frame, LightDetectionSettings())

    assert len(processed.observations) == 1
    source = processed.observations[0]
    assert source.detection_method == "peak core"
    assert source.center[0] == pytest.approx(95.0, abs=3.0)
    assert source.center[1] == pytest.approx(75.0, abs=3.0)


def test_tracker_keeps_stable_ids_when_confidence_order_changes():
    tracker = LightSourceTracker(
        smoothing_alpha=1.0,
        match_distance_px=40.0,
        max_sources=4,
    )
    first = tracker.update([
        _candidate(60.0, confidence=0.95),
        _candidate(220.0, confidence=0.70),
    ])
    first_ids = {round(source.image_center[0]): source.stable_id
                 for source in first}

    second = tracker.update([
        _candidate(215.0, confidence=0.99, timestamp=2.0),
        _candidate(65.0, confidence=0.60, timestamp=2.0),
    ])
    second_ids = {round(source.image_center[0]): source.stable_id
                  for source in second}

    assert first_ids[60] == second_ids[65]
    assert first_ids[220] == second_ids[215]
    assert all(source.state == "tracked" for source in second)


def test_single_source_tracker_replaces_a_stale_false_candidate_immediately():
    tracker = LightSourceTracker(
        smoothing_alpha=1.0,
        hold_frames=5,
        match_distance_px=30.0,
        max_sources=1,
    )
    first = tracker.update([_candidate(45.0, confidence=0.90)])

    second = tracker.update([
        _candidate(240.0, confidence=0.80, timestamp=2.0),
    ])

    assert len(second) == 1
    assert second[0].stable_id != first[0].stable_id
    assert second[0].image_center[0] == pytest.approx(240.0)
    assert second[0].state == "new"


def test_bright_strip_spanning_frame_is_not_a_point_source():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(frame, (135, 0), (175, 239), (255, 255, 255), -1)

    processed = process_bright_spots(frame, LightDetectionSettings())

    assert processed.observations == ()


class _Scene:
    def update_eyes(self, eyes):
        self.eyes = tuple(eyes)

    def update_lights(self, lights):
        self.lights = tuple(lights)

    def update_eye_rays(self, eyes, lights):
        self.rays = tuple((eye, light) for light in lights for eye in eyes)

    def update_intersections(self, intersections):
        self.intersections = tuple(intersections)

    def update_windshield(self, width, height):
        pass

    def update_camera(self, *position):
        pass


class _Windshield:
    def update_glares(self, glares, has_out):
        self.glares = tuple(glares)

    def clear_glare(self):
        self.glares = ()

    def set_windshield_aspect(self, width, height):
        pass


class _Readout:
    def set_value(self, *args):
        pass

    def set_intersections(self, intersections):
        self.intersections = tuple(intersections)


class _LCD:
    def __init__(self):
        self.cleared = 0
        self.updated = []

    def clear_output(self):
        self.cleared += 1

    def update_intersections(self, intersections):
        self.updated.append(tuple(intersections))


class _AutoControls:
    def is_auto_light(self):
        return True

    def get_light_positions(self):
        raise AssertionError("camera lights must not use vehicle offsets")

    def get_windshield_dims(self):
        return (40.0, 20.0)

    def get_camera_pos(self):
        return (0.0, 0.0, 20.0)

    def mode_policy(self):
        return SimpleNamespace(manual_driver=False)


def test_camera_geometry_uses_complete_source_list_without_vehicle_offsets():
    scene = _Scene()
    readout = _Readout()
    tracker = TrackingController(
        scene, _Windshield(), readout, _AutoControls())
    sources = [
        TrackedLightSource(
            "L7", (-8.0, 120.0, 10.0), 1.0, 0.9, "tracked",
            (80.0, 100.0), 12.0,
        ),
        TrackedLightSource(
            "L9", (8.0, 120.0, 10.0), 1.0, 0.85, "tracked",
            (220.0, 100.0), 12.0,
        ),
    ]

    tracker.on_lights_detected(sources, calculate=False)
    tracker.on_eyes_detected(-3.0, -50.0, 10.0, 3.0, -50.0, 10.0)

    assert scene.lights == (sources[0].position, sources[1].position)
    assert len(scene.rays) == 4
    assert [entry[0] for entry in readout.intersections] == [
        "L7/E1", "L7/E2", "L9/E1", "L9/E2",
    ]


def test_rough_uncalibrated_preview_never_reaches_geometry_or_lcd():
    scene, windshield, readout, lcd = _Scene(), _Windshield(), _Readout(), _LCD()
    tracker = TrackingController(
        scene, windshield, readout, _AutoControls(), lcd_blocker=lcd)
    rough = TrackedLightSource(
        "L1", (5.0, 120.0, 12.0), 1.0, 0.3, "new",
        (160.0, 120.0), 10.0, (150.0, 122.0),
    )

    tracker.preview_uncalibrated_lights([rough])

    assert scene.lights == (rough.position,)
    assert scene.intersections == ()
    assert windshield.glares == ()
    assert lcd.cleared == 1
    assert lcd.updated == []
    assert tracker._live_light_sources == ()
