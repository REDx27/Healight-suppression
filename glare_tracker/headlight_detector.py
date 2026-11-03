"""Stereo headlight detection using two USB webcams.

Detects bright spots in sequentially grabbed (not hardware-synchronized) frames
and triangulates its 3D position in real-time.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, replace
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

from glare_tracker.calibration import (
    MonocularRangeCalibration,
    StereoCalibrationResult,
    load_monocular_range_calibration,
    load_stereo_calibration,
    stereo_profile_name,
    stereo_profile_compatible,
)
from glare_tracker.capture import configure_video_capture, open_video_capture
from glare_tracker.light_sources import (
    LightCandidate,
    LightSourceTracker,
    TrackedLightSource,
)


PREVIEW_MODES = (
    "Detection overlay",
    "Original",
    "Threshold mask",
    "Peak-core mask",
    "Background difference",
    "Multi-scale saliency",
    "Local contrast",
    "Intensity (all colors)",
    "Blurred intensity",
)


@dataclass(frozen=True)
class LightDetectionSettings:
    """Live-tunable camera and bright-source detector settings."""

    brightness_threshold: int = 200
    adaptive_threshold: bool = True
    min_area_px: float = 5.0
    max_area_px: float = 50000.0
    blur_size: int = 3
    morphology_iterations: int = 1
    max_sources: int = 1
    match_distance_px: float = 80.0
    require_local_contrast: bool = True
    local_contrast_threshold: int = 8
    minimum_confidence: float = 0.25
    background_rejection: bool = False
    background_difference_threshold: int = 30
    apply_camera_controls: bool = False
    auto_exposure: bool = True
    exposure: float = -6.0
    brightness: float = 128.0
    contrast: float = 128.0
    gain: float = 0.0

    def normalized(self) -> "LightDetectionSettings":
        blur = max(1, int(self.blur_size))
        if blur % 2 == 0:
            blur += 1
        return replace(
            self,
            brightness_threshold=int(np.clip(
                self.brightness_threshold, 0, 255)),
            min_area_px=max(0.0, float(self.min_area_px)),
            max_area_px=max(
                float(self.min_area_px), float(self.max_area_px)),
            blur_size=min(31, blur),
            morphology_iterations=max(
                0, min(5, int(self.morphology_iterations))),
            max_sources=max(1, min(8, int(self.max_sources))),
            match_distance_px=max(1.0, float(self.match_distance_px)),
            local_contrast_threshold=int(np.clip(
                self.local_contrast_threshold, 1, 255)),
            minimum_confidence=float(np.clip(
                self.minimum_confidence, 0.0, 1.0)),
            background_difference_threshold=int(np.clip(
                self.background_difference_threshold, 1, 255)),
        )


class TemporalPointFilter:
    """Smooth a tracked point and bridge a few dropped detections.

    Camera exposure changes and threshold noise can make an otherwise steady
    light disappear for one or two frames.  Keeping the last position briefly
    prevents that normal noise from flickering the UI and windshield marker.
    """

    def __init__(
        self, alpha: float = 0.32, hold_frames: int = 5,
        max_step: Optional[float] = None,
    ):
        self.alpha = float(np.clip(alpha, 0.01, 1.0))
        self.hold_frames = max(0, int(hold_frames))
        self.max_step = max_step
        self._point: Optional[np.ndarray] = None
        self._missing_frames = 0

    @property
    def point(self) -> Optional[tuple[float, ...]]:
        if self._point is None:
            return None
        return tuple(float(value) for value in self._point)

    def update(self, measurement) -> Optional[tuple[float, ...]]:
        if measurement is None:
            self._missing_frames += 1
            if self._point is not None and self._missing_frames <= self.hold_frames:
                return self.point
            self._point = None
            return None

        measured = np.asarray(measurement, dtype=np.float64)
        self._missing_frames = 0
        if self._point is None or self._point.shape != measured.shape:
            self._point = measured
            return self.point

        delta = measured - self._point
        if self.max_step is not None:
            distance = float(np.linalg.norm(delta))
            if distance > self.max_step > 0:
                delta *= self.max_step / distance
        self._point = self._point + self.alpha * delta
        return self.point


@dataclass(frozen=True)
class BrightSpotObservation:
    """Detected light centre, size, confidence, and visible bounds."""

    center: tuple[float, float]
    diameter_px: float
    area_px: float
    confidence: float = 1.0
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)
    detection_method: str = "saliency"


@dataclass(frozen=True)
class DetectionFrame:
    """Intermediate images and measurements used by preview modes."""

    observations: tuple[BrightSpotObservation, ...]
    gray: np.ndarray
    blurred: np.ndarray
    mask: np.ndarray
    peak_mask: np.ndarray
    difference: np.ndarray
    saliency: np.ndarray
    local_contrast: np.ndarray
    threshold_used: float
    saliency_threshold: float
    background: float
    peak: float


def _light_intensity(frame: np.ndarray) -> np.ndarray:
    """Return a light-sensitive image that does not penalize coloured LEDs."""

    if len(frame.shape) == 2:
        return frame.copy()
    # Standard grayscale gives saturated red only about 30% of its sensor
    # value. The strongest-channel image treats white, amber, red, and blue
    # emitters consistently while still remaining an 8-bit scalar image.
    return np.max(frame, axis=2).astype(np.uint8)


def _neutral_light_intensity(frame: np.ndarray) -> np.ndarray:
    """Return intensity shared by every channel for clipped white cores.

    Skin and reddish reflections can saturate only the red channel. Taking the
    weakest channel prevents those regions from masquerading as a white lamp,
    while coloured emitters remain handled by the multi-scale saliency path.
    """

    if len(frame.shape) == 2:
        return frame.copy()
    return np.min(frame, axis=2).astype(np.uint8)


def _multiscale_directional_contrast(intensity: np.ndarray) -> np.ndarray:
    """Enhance compact peaks while suppressing broad regions and edges.

    At each scale, the mean central patch must be brighter than every one of
    its eight surrounding patches. Taking the maximum response across scales
    covers tiny distant lamps and large nearby saturated lamps without making
    one kernel size decide the result.
    """

    image = intensity.astype(np.float32)
    height, width = image.shape
    saliency = np.zeros_like(image, dtype=np.float32)
    maximum_patch = max(3, min(height, width) // 3)
    patch_sizes = [
        size for size in (3, 7, 15, 31, 63, 95)
        if size <= maximum_patch
    ]
    for size in patch_sizes:
        patch_mean = cv2.boxFilter(
            image,
            cv2.CV_32F,
            (size, size),
            normalize=True,
            borderType=cv2.BORDER_REFLECT101,
        )
        pad = size
        padded = cv2.copyMakeBorder(
            patch_mean,
            pad,
            pad,
            pad,
            pad,
            cv2.BORDER_REFLECT101,
        )
        neighbours = []
        for dy, dx in (
            (-size, -size), (-size, 0), (-size, size),
            (0, -size), (0, size),
            (size, -size), (size, 0), (size, size),
        ):
            y0 = pad + dy
            x0 = pad + dx
            neighbours.append(padded[y0:y0 + height, x0:x0 + width])
        surround = np.maximum.reduce(neighbours)
        saliency = np.maximum(saliency, np.maximum(patch_mean - surround, 0.0))
    return saliency


def process_bright_spots(
    frame: np.ndarray,
    settings: Optional[LightDetectionSettings] = None,
    background_gray: Optional[np.ndarray] = None,
) -> DetectionFrame:
    """Run the complete, inspectable multi-source detection pipeline."""

    settings = (settings or LightDetectionSettings()).normalized()
    gray = _light_intensity(frame)
    neutral_intensity = _neutral_light_intensity(frame)
    # A broad bright surface and a compact lamp can have the same absolute
    # intensity. Subtracting a large local illumination estimate keeps point-
    # like highlights while suppressing flat window interiors.
    local_illumination = cv2.GaussianBlur(gray, (51, 51), 0)
    local_contrast = cv2.subtract(gray, local_illumination)
    saliency_float = _multiscale_directional_contrast(gray)
    saliency = np.clip(saliency_float, 0, 255).astype(np.uint8)

    difference = np.zeros_like(gray)
    changed = None
    if (settings.background_rejection
            and background_gray is not None
            and background_gray.shape == gray.shape):
        # Compensate for the global brightness shift caused by auto exposure
        # before comparing frames. Without this, switching on one lamp can
        # make the whole window look like a moving source.
        valid = (gray < 245) & (background_gray < 245)
        offset = 0.0
        if int(np.count_nonzero(valid)) >= 100:
            offset = float(np.median(gray[valid])) - float(
                np.median(background_gray[valid]))
        aligned_background = np.clip(
            background_gray.astype(np.float32) + offset, 0, 255,
        ).astype(np.uint8)
        difference = cv2.absdiff(gray, aligned_background)
        _, changed = cv2.threshold(
            difference,
            settings.background_difference_threshold,
            255,
            cv2.THRESH_BINARY,
        )

    blurred = (
        cv2.GaussianBlur(
            gray,
            (settings.blur_size, settings.blur_size),
            0,
        )
        if settings.blur_size > 1 else gray.copy()
    )
    peak_blurred = (
        cv2.GaussianBlur(
            neutral_intensity,
            (settings.blur_size, settings.blur_size),
            0,
        )
        if settings.blur_size > 1 else neutral_intensity.copy()
    )

    background = float(np.median(blurred))
    peak = float(np.max(blurred))
    saliency_mean = float(np.mean(saliency_float))
    saliency_std = float(np.std(saliency_float))
    saliency_peak = float(np.max(saliency_float))
    # MPCM-style statistical segmentation (mean + K*sigma), bounded below
    # by the operator's contrast floor and below the strongest response so a
    # large nearby lamp cannot raise its own threshold out of existence.
    statistical_threshold = saliency_mean + 2.5 * saliency_std
    saliency_threshold = max(
        float(settings.local_contrast_threshold),
        min(statistical_threshold, 0.75 * saliency_peak),
    )
    requested_threshold = float(settings.brightness_threshold)
    if settings.adaptive_threshold:
        # The configured value is a ceiling in adaptive mode. Basing the
        # threshold on the brightest pixel made a bright window force the
        # threshold upward and hide a dimmer-but-distinct phone lamp. The
        # median represents the ordinary scene while local/background gates
        # below decide whether a bright region is actually a source.
        contrast_margin = 12.0 if settings.require_local_contrast else 18.0
        threshold = max(
            25.0,
            min(requested_threshold, background + contrast_margin),
        )
        valid_contrast = peak > threshold
    else:
        threshold = requested_threshold
        valid_contrast = peak > threshold

    # Independent peak-core evidence protects saturated lamps with a broad,
    # flat halo. Such a lamp can have weak centre-versus-neighbour contrast
    # even though its clipped core is unambiguous in the camera image.
    peak_background = float(np.median(peak_blurred))
    neutral_peak = float(np.max(peak_blurred))
    peak_percentile = float(np.percentile(peak_blurred, 99.5))
    peak_threshold = max(
        peak_background + 15.0,
        min(245.0, peak_percentile, neutral_peak - 3.0),
    )
    has_peak_core = (
        neutral_peak >= peak_threshold
        and neutral_peak - peak_background >= 20.0
    )
    if settings.require_local_contrast:
        valid_contrast = (
            valid_contrast
            and (saliency_peak >= saliency_threshold or has_peak_core)
        )

    if not valid_contrast or threshold >= 255.0:
        mask = np.zeros_like(gray)
        return DetectionFrame(
            (), gray, blurred, mask, mask.copy(), difference, saliency,
            local_contrast,
            threshold, saliency_threshold, background, peak)

    _, brightness_mask = cv2.threshold(
        blurred, min(254.0, threshold), 255, cv2.THRESH_BINARY)
    _, peak_mask = cv2.threshold(
        peak_blurred, min(254.0, peak_threshold), 255, cv2.THRESH_BINARY)
    if settings.require_local_contrast:
        _, saliency_mask = cv2.threshold(
            saliency,
            min(254.0, saliency_threshold),
            255,
            cv2.THRESH_BINARY,
        )
        saliency_candidates = cv2.bitwise_and(
            brightness_mask, saliency_mask)
    else:
        saliency_candidates = brightness_mask.copy()
    peak_candidates = peak_mask.copy()
    if changed is not None:
        saliency_candidates = cv2.bitwise_and(
            saliency_candidates, changed)
        peak_candidates = cv2.bitwise_and(peak_candidates, changed)
    if settings.morphology_iterations:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        saliency_candidates = cv2.morphologyEx(
            saliency_candidates,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=settings.morphology_iterations,
        )
        saliency_candidates = cv2.morphologyEx(
            saliency_candidates,
            cv2.MORPH_OPEN,
            kernel,
            iterations=settings.morphology_iterations,
        )
        # Do not open the peak mask. A distant clipped emitter may only have
        # one or two peak pixels and must remain observable.
        peak_candidates = cv2.morphologyEx(
            peak_candidates,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=settings.morphology_iterations,
        )

    mask = cv2.bitwise_or(saliency_candidates, peak_candidates)

    saliency_contours, _ = cv2.findContours(
        saliency_candidates, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    peak_contours, _ = cv2.findContours(
        peak_candidates, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidate_contours = (
        [(contour, False, saliency_candidates)
         for contour in saliency_contours]
        + [(contour, True, peak_candidates) for contour in peak_contours]
    )
    observations = []
    frame_area = float(gray.shape[0] * gray.shape[1])
    for contour, is_peak_core, candidate_mask in candidate_contours:
        area = float(cv2.contourArea(contour))
        minimum_area = 0.0 if is_peak_core else settings.min_area_px
        maximum_area = (
            max(settings.max_area_px, frame_area * 0.30)
            if is_peak_core else settings.max_area_px
        )
        if area < minimum_area or area > maximum_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        minimum_aspect = 0.03 if is_peak_core else 0.2
        maximum_aspect = 30.0 if is_peak_core else 5.0
        if h == 0 or not minimum_aspect <= (w / h) <= maximum_aspect:
            continue
        roi_saliency = saliency_float[y:y+h, x:x+w]
        candidate_saliency = float(np.max(roi_saliency))
        if (not is_peak_core
                and settings.require_local_contrast
                and candidate_saliency < saliency_threshold
                and float(np.max(peak_blurred[y:y+h, x:x+w]))
                < peak_threshold):
            continue
        roi_gray = gray[y:y+h, x:x+w].astype(np.float64)
        roi_neutral = neutral_intensity[y:y+h, x:x+w].astype(np.float64)
        roi_mask = candidate_mask[y:y+h, x:x+w] > 0
        core_radius = None
        if is_peak_core:
            distance_map = cv2.distanceTransform(
                roi_mask.astype(np.uint8) * 255,
                cv2.DIST_L2,
                5,
            )
            core_radius = float(np.max(distance_map))
            # A thin saturated flare may connect the lamp to another white
            # structure. Squared distance-transform weights locate the
            # thickest core instead of pulling the centre along that trail.
            weights = (
                np.square(distance_map.astype(np.float64)) * roi_neutral)
        else:
            weights = roi_gray * roi_mask
        total_weight = float(np.sum(weights))
        if total_weight <= 0:
            continue

        y_grid, x_grid = np.indices(weights.shape)
        cx = float(x + np.sum(x_grid * weights) / total_weight)
        cy = float(y + np.sum(y_grid * weights) / total_weight)
        mean_brightness = float(np.mean(roi_gray[roi_mask]))
        local_peak = float(np.max(roi_gray))
        perimeter = float(cv2.arcLength(contour, True))
        compactness = (
            4.0 * np.pi * area / (perimeter * perimeter)
            if perimeter > 0 else 0.0
        )
        contrast_score = min(1.0, candidate_saliency / 80.0)
        brightness_score = float(np.clip(
            (mean_brightness - threshold) / max(30.0, 255.0 - threshold),
            0.0,
            1.0,
        ))
        saturated_fraction = float(np.mean(roi_neutral[roi_mask] >= 245.0))
        local_neutral_peak = float(np.max(roi_neutral))
        peak_score = float(np.clip(
            (local_neutral_peak - peak_threshold)
            / max(3.0, 255.0 - peak_threshold),
            0.0,
            1.0,
        ))
        confidence = float(np.clip(
            0.40 * contrast_score
            + 0.15 * brightness_score
            + 0.15 * np.clip(compactness, 0.0, 1.0)
            + 0.10 * min(1.0, area / 80.0)
            + 0.15 * peak_score
            + 0.05 * min(1.0, saturated_fraction * 4.0),
            0.0,
            1.0,
        ))
        required_confidence = settings.minimum_confidence
        if changed is not None:
            required_confidence *= 0.80
        if is_peak_core:
            confidence = max(
                confidence,
                float(np.clip(
                    0.30
                    + 0.35 * peak_score
                    + 0.15 * np.clip(compactness, 0.0, 1.0)
                    + 0.10 * min(1.0, area / 40.0)
                    + 0.10 * min(1.0, saturated_fraction * 4.0),
                    0.0,
                    1.0,
                )),
            )
            required_confidence = min(required_confidence, 0.25)
        if confidence < required_confidence:
            continue
        diameter_px = (
            max(1.0, 2.0 * core_radius)
            if core_radius is not None
            else 2.0 * np.sqrt(area / np.pi)
        )
        observations.append(BrightSpotObservation(
            center=(cx, cy),
            diameter_px=float(diameter_px),
            area_px=area,
            confidence=confidence,
            bounds=(x, y, w, h),
            detection_method=("peak core" if is_peak_core else "saliency"),
        ))

    observations.sort(
        key=lambda item: (
            item.detection_method == "peak core",
            item.confidence,
            item.area_px,
        ),
        reverse=True,
    )
    deduplicated = []
    for observation in observations:
        duplicate = False
        for accepted in deduplicated:
            distance = float(np.hypot(
                observation.center[0] - accepted.center[0],
                observation.center[1] - accepted.center[1],
            ))
            merge_distance = max(
                6.0,
                0.45 * max(
                    observation.diameter_px,
                    accepted.diameter_px,
                ),
            )
            if distance <= merge_distance:
                duplicate = True
                break
        if not duplicate:
            deduplicated.append(observation)
    return DetectionFrame(
        tuple(deduplicated[:settings.max_sources]),
        gray,
        blurred,
        mask,
        peak_candidates,
        difference,
        saliency,
        local_contrast,
        threshold,
        saliency_threshold,
        background,
        peak,
    )


def detect_bright_spot_observations(
    frame: np.ndarray,
    settings: Optional[LightDetectionSettings] = None,
) -> list[BrightSpotObservation]:
    """Return all accepted bright-source candidates in confidence order."""

    return list(process_bright_spots(frame, settings).observations)


def detect_bright_spot_observation(
    frame: np.ndarray, thresh_val: int = 210, min_area: float = 5.0,
    max_area: float = 50000.0,
    previous_point: Optional[tuple[float, float]] = None,
) -> Optional[BrightSpotObservation]:
    """Detect a compact light source using contrast and weighted centroid.

    The threshold is combined with the frame's background level so exposure
    changes do not turn ordinary bright surfaces into headlights.  When more
    than one candidate exists, proximity to the previous result discourages
    the detector from jumping between sources.
    """
    settings = LightDetectionSettings(
        brightness_threshold=thresh_val,
        min_area_px=min_area,
        max_area_px=max_area,
        max_sources=8,
    )
    candidates = detect_bright_spot_observations(frame, settings)
    if not candidates:
        return None
    if previous_point is None:
        return candidates[0]
    return max(
        candidates,
        key=lambda candidate: (
            candidate.confidence
            - min(0.45, 0.003 * float(np.hypot(
                candidate.center[0] - previous_point[0],
                candidate.center[1] - previous_point[1],
            )))
        ),
    )


def detect_bright_spot(
    frame: np.ndarray, thresh_val: int = 210, min_area: float = 5.0,
    max_area: float = 10000.0,
    previous_point: Optional[tuple[float, float]] = None,
) -> Optional[tuple[float, float]]:
    """Backward-compatible centre-only bright-spot detector."""
    observation = detect_bright_spot_observation(
        frame, thresh_val, min_area, max_area, previous_point)
    return None if observation is None else observation.center


def _apply_camera_controls(capture, settings: LightDetectionSettings):
    """Apply UVC controls and return driver acceptance plus actual readback."""

    accepted = {}
    if not settings.apply_camera_controls:
        # Explicitly return to automatic exposure after an earlier manual
        # tuning session; many webcam drivers retain the last manual value.
        accepted["auto_exposure"] = bool(capture.set(
            cv2.CAP_PROP_AUTO_EXPOSURE, 0.75))
    else:
        accepted["auto_exposure"] = bool(capture.set(
            cv2.CAP_PROP_AUTO_EXPOSURE,
            0.75 if settings.auto_exposure else 0.25,
        ))
        if not settings.auto_exposure:
            accepted["exposure"] = bool(capture.set(
                cv2.CAP_PROP_EXPOSURE, float(settings.exposure)))
        accepted["brightness"] = bool(capture.set(
            cv2.CAP_PROP_BRIGHTNESS, float(settings.brightness)))
        accepted["contrast"] = bool(capture.set(
            cv2.CAP_PROP_CONTRAST, float(settings.contrast)))
        accepted["gain"] = bool(capture.set(
            cv2.CAP_PROP_GAIN, float(settings.gain)))

    return {
        "enabled": settings.apply_camera_controls,
        "auto_exposure_requested": settings.auto_exposure,
        "exposure_requested": float(settings.exposure),
        "accepted": accepted,
        "actual": {
            "auto_exposure": float(capture.get(cv2.CAP_PROP_AUTO_EXPOSURE)),
            "exposure": float(capture.get(cv2.CAP_PROP_EXPOSURE)),
            "brightness": float(capture.get(cv2.CAP_PROP_BRIGHTNESS)),
            "contrast": float(capture.get(cv2.CAP_PROP_CONTRAST)),
            "gain": float(capture.get(cv2.CAP_PROP_GAIN)),
        },
    }


def _preview_frame(
    frame: np.ndarray,
    processed: DetectionFrame,
    sources: list[TrackedLightSource],
    preview_mode: str,
    settings: LightDetectionSettings,
    secondary: bool = False,
) -> np.ndarray:
    """Build an operator-facing view of a selected processing stage."""

    if preview_mode == "Original":
        return frame.copy()
    elif preview_mode == "Threshold mask":
        preview = cv2.cvtColor(processed.mask, cv2.COLOR_GRAY2BGR)
    elif preview_mode == "Peak-core mask":
        preview = cv2.cvtColor(processed.peak_mask, cv2.COLOR_GRAY2BGR)
    elif preview_mode == "Background difference":
        preview = cv2.cvtColor(processed.difference, cv2.COLOR_GRAY2BGR)
    elif preview_mode == "Multi-scale saliency":
        preview = cv2.applyColorMap(processed.saliency, cv2.COLORMAP_TURBO)
    elif preview_mode == "Local contrast":
        preview = cv2.cvtColor(processed.local_contrast, cv2.COLOR_GRAY2BGR)
    elif preview_mode == "Intensity (all colors)":
        preview = cv2.cvtColor(processed.gray, cv2.COLOR_GRAY2BGR)
    elif preview_mode == "Blurred intensity":
        preview = cv2.cvtColor(processed.blurred, cv2.COLOR_GRAY2BGR)
    else:
        preview = frame.copy()
        for observation in processed.observations:
            x, y, w, h = observation.bounds
            cv2.rectangle(preview, (x, y), (x + w, y + h), (60, 190, 255), 1)
            cv2.putText(
                preview,
                f"{observation.detection_method} {observation.confidence:.0%}",
                (x, max(42, y - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (60, 190, 255),
                1,
                cv2.LINE_AA,
            )
        for source in sources:
            center = (
                source.secondary_image_center if secondary
                else source.image_center
            )
            if center is None:
                continue
            u, v = int(round(center[0])), int(round(center[1]))
            color = (
                (0, 180, 255)
                if source.state == "temporarily_lost" else (0, 255, 80)
            )
            cv2.circle(preview, (u, v), 11, color, 2)
            cv2.putText(
                preview,
                f"{source.stable_id} {source.confidence:.0%}",
                (u + 13, max(18, v - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                color,
                1,
                cv2.LINE_AA,
            )

    mode_label = preview_mode.upper()
    cv2.rectangle(preview, (0, 0), (preview.shape[1], 25), (5, 8, 14), -1)
    cv2.putText(
        preview,
        f"{mode_label}  candidates:{len(processed.observations)}  "
        f"brightness:{processed.threshold_used:.0f}  "
        f"saliency:{processed.saliency_threshold:.0f}",
        (8, 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.46,
        (120, 225, 255),
        1,
        cv2.LINE_AA,
    )
    if preview_mode == "Detection overlay":
        exposure_label = (
            "camera defaults"
            if not settings.apply_camera_controls else
            "auto exposure"
            if settings.auto_exposure else f"exposure {settings.exposure:g}"
        )
        cv2.putText(
            preview,
            exposure_label,
            (8, preview.shape[0] - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.44,
            (255, 220, 100),
            1,
            cv2.LINE_AA,
        )
    return preview


def _to_qimage(frame: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    return QImage(
        rgb.data, width, height, width * 3, QImage.Format_RGB888,
    ).copy()


def _safe_release(capture):
    if capture is None:
        return
    try:
        capture.release()
    except cv2.error:
        # Some Windows camera backends throw while an interrupted read is
        # unwinding. The device is already being torn down at this point.
        pass


def _match_stereo_candidates(
    primary: DetectionFrame,
    secondary: DetectionFrame,
    calibration: Optional[StereoCalibrationResult],
    frame_shape: tuple[int, ...],
    camera_height_cm: float,
) -> list[LightCandidate]:
    """Pair independent bright candidates and triangulate each valid pair."""
    if calibration is None:
        return []  # Uncalibrated previews are useful; invented metric depth is not.
    projected_primary = []
    projected_secondary = []
    for observations, camera, rotation, projection, output in (
        (primary.observations, calibration.cam1, calibration.R1, calibration.P1, projected_primary),
        (secondary.observations, calibration.cam2, calibration.R2, calibration.P2, projected_secondary),
    ):
        for observation in observations:
            point = np.array([[observation.center]], dtype=np.float32)
            rectified = cv2.undistortPoints(
                point, camera.camera_matrix, camera.dist_coeffs,
                R=rotation, P=projection,
            )[0, 0]
            output.append(tuple(float(value) for value in rectified))

    possible_pairs = []
    for primary_index, (x1, y1) in enumerate(projected_primary):
        for secondary_index, (x2, y2) in enumerate(projected_secondary):
            row_error = abs(y1 - y2)
            disparity = x1 - x2
            if row_error <= 3.0 and disparity > 0.1:
                confidence = (
                    primary.observations[primary_index].confidence
                    + secondary.observations[secondary_index].confidence
                ) / 2.0
                possible_pairs.append((
                    row_error - 4.0 * confidence,
                    primary_index,
                    secondary_index,
                    disparity,
                    row_error,
                ))

    used_primary = set()
    used_secondary = set()
    candidates = []
    for _, primary_index, secondary_index, disparity, row_error in sorted(
            possible_pairs):
        if (primary_index in used_primary
                or secondary_index in used_secondary):
            continue
        used_primary.add(primary_index)
        used_secondary.add(secondary_index)

        x1, y1 = projected_primary[primary_index]
        focal = float(calibration.P1[0, 0])
        cx = float(calibration.P1[0, 2])
        cy = float(calibration.P1[1, 2])
        baseline_cm = float(calibration.baseline_cm)

        depth_cm = focal * baseline_cm / disparity
        if not 5.0 <= depth_cm <= 10000.0:
            continue
        camera_x_cm = (x1 - cx) * depth_cm / focal
        camera_y_cm = (y1 - cy) * depth_cm / focal
        position = (
            camera_x_cm - baseline_cm / 2.0,
            depth_cm,
            -camera_y_cm + camera_height_cm,
        )
        first = primary.observations[primary_index]
        second = secondary.observations[secondary_index]
        confidence = float(np.clip(
            ((first.confidence + second.confidence) / 2.0)
            * (1.0 - min(0.5, row_error / 40.0)),
            0.0,
            1.0,
        ))
        candidates.append(LightCandidate(
            position=position,
            image_center=first.center,
            secondary_image_center=second.center,
            diameter_px=(first.diameter_px + second.diameter_px) / 2.0,
            confidence=confidence,
            timestamp=time.time(),
        ))
    return candidates


class MonocularHeadlightDetectorThread(QThread):
    """Detect and track independent light sources with one outward camera.

    A single camera cannot measure depth on its own, so ``depth_cm`` is a
    user-provided distance.  The image point is projected onto that depth
    plane with the camera mounted at the windshield's top-centre.
    """

    frame_ready = pyqtSignal(QImage)
    headlight_detected = pyqtSignal(float, float, float)
    lights_detected = pyqtSignal(object)
    light_observed = pyqtSignal(float, float, float, int, int)
    headlight_lost = pyqtSignal()
    camera_status = pyqtSignal(str, bool)
    camera_controls_report = pyqtSignal(object)
    background_status = pyqtSignal(str)
    pipeline_timing = pyqtSignal(object)

    def __init__(
        self, camera_index: int = 1, depth_cm: float = 120.0,
        windshield_h_cm: float = 19.5, hfov_deg: float = 70.0,
        brightness_threshold: int = 210,
        detection_settings: Optional[LightDetectionSettings] = None,
        use_range_calibration: bool = True, parent=None,
    ):
        super().__init__(parent)
        self.camera_index = camera_index
        self.depth_cm = depth_cm
        self.windshield_h_cm = windshield_h_cm
        self.hfov_deg = hfov_deg
        self.detection_settings = (
            detection_settings
            or LightDetectionSettings(
                brightness_threshold=brightness_threshold)
        ).normalized()
        self.brightness_threshold = self.detection_settings.brightness_threshold
        self.preview_mode = PREVIEW_MODES[0]
        self._settings_revision = 0
        self._running = False
        self._background_gray: Optional[np.ndarray] = None
        self._capture_background_requested = False
        self._source_tracker = LightSourceTracker(
            smoothing_alpha=0.32,
            hold_frames=5,
            match_distance_px=self.detection_settings.match_distance_px,
            max_sources=self.detection_settings.max_sources,
        )
        self._range_calibration: Optional[MonocularRangeCalibration] = None
        if use_range_calibration:
            try:
                calibration = load_monocular_range_calibration()
                if calibration is not None and calibration.camera_index == camera_index:
                    self._range_calibration = calibration
            except Exception:
                self._range_calibration = None

    def update_projection(
        self, depth_cm: float, windshield_h_cm: float, hfov_deg: float,
        brightness_threshold: int,
    ):
        self.depth_cm = depth_cm
        self.windshield_h_cm = windshield_h_cm
        self.hfov_deg = hfov_deg
        self.brightness_threshold = brightness_threshold
        self.detection_settings = replace(
            self.detection_settings,
            brightness_threshold=int(brightness_threshold),
        ).normalized()
        self._settings_revision += 1

    def update_detection_settings(self, settings: LightDetectionSettings):
        self.detection_settings = settings.normalized()
        self.brightness_threshold = self.detection_settings.brightness_threshold
        self._settings_revision += 1

    def set_preview_mode(self, preview_mode: str):
        if preview_mode in PREVIEW_MODES:
            self.preview_mode = preview_mode

    def capture_background(self):
        self._capture_background_requested = True

    def clear_background(self):
        self._background_gray = None
        self._capture_background_requested = False
        self.background_status.emit("Background reference cleared")

    def set_range_calibration(
        self, calibration: Optional[MonocularRangeCalibration],
    ):
        """Enable or clear reference-size ranging while the thread runs."""
        self._range_calibration = calibration

    def stop(self):
        self._running = False
        if self.isRunning():
            self.wait(5000)

    def run(self):
        self._running = True
        cap = None
        try:
            cap, backend_name = open_video_capture(self.camera_index)
            if cap is None:
                self.camera_status.emit(
                    f"Camera {self.camera_index} not detected", False)
                self.headlight_lost.emit()
                return

            # Many inexpensive USB cameras fall back to a very slow raw-video
            # mode at 720p.  MJPEG 640x480 is widely supported and keeps the
            # monocular tracker responsive while retaining enough resolution
            # for a bright-source centroid.
            width, height, _ = configure_video_capture(cap)
            report = _apply_camera_controls(cap, self.detection_settings)
            self.camera_controls_report.emit(report)
            applied_settings_revision = self._settings_revision
            self.camera_status.emit(
                f"Camera {self.camera_index} connected via {backend_name} "
                f"({width}x{height}, single)", True)

            lost_announced = False
            frame_number = 0
            brightness_90 = 0.0
            measured_fps = 0.0
            fps_frames = 0
            fps_started = time.monotonic()
            while self._running:
                capture_started_ns = time.monotonic_ns()
                ok, frame = cap.read()
                if not ok:
                    self.camera_status.emit(
                        f"Camera {self.camera_index} frame unavailable", False)
                    self.msleep(30)
                    continue
                capture_complete_ns = time.monotonic_ns()

                if applied_settings_revision != self._settings_revision:
                    report = _apply_camera_controls(
                        cap, self.detection_settings)
                    self.camera_controls_report.emit(report)
                    self._source_tracker.configure(
                        self.detection_settings.match_distance_px,
                        self.detection_settings.max_sources,
                    )
                    applied_settings_revision = self._settings_revision

                if self._capture_background_requested:
                    self._background_gray = _light_intensity(frame)
                    self._capture_background_requested = False
                    self.background_status.emit(
                        "Background captured — introduce the test light now")

                frame_number += 1
                # Observe exposure without forcing vendor-specific controls.
                # Most inexpensive webcams are more reliable in their default
                # auto-exposure mode; detection adapts in software instead.
                if frame_number % 8 == 0:
                    sample = cv2.resize(frame, (160, 120))
                    sample_gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
                    brightness_90 = float(np.percentile(sample_gray, 90.0))

                fps_frames += 1
                fps_elapsed = time.monotonic() - fps_started
                if fps_elapsed >= 1.0:
                    measured_fps = fps_frames / fps_elapsed
                    fps_frames = 0
                    fps_started = time.monotonic()

                settings = self.detection_settings
                processed = process_bright_spots(
                    frame, settings, self._background_gray)
                h, w = frame.shape[:2]
                hfov = np.deg2rad(np.clip(self.hfov_deg, 10.0, 170.0))
                fx = (w / 2.0) / np.tan(hfov / 2.0)
                fy = fx
                candidates = []
                for observation in processed.observations:
                    if self._range_calibration is not None:
                        reference_width = self._range_calibration.image_size[0]
                        normalized_diameter = (
                            observation.diameter_px * reference_width / max(1, w)
                        )
                        depth = self._range_calibration.estimate_distance_cm(
                            normalized_diameter)
                        depth = float(np.clip(depth, 10.0, 5000.0))
                    else:
                        depth = max(1.0, float(self.depth_cm))
                    u, v = observation.center
                    candidates.append(LightCandidate(
                        position=(
                            (u - w / 2.0) * depth / fx,
                            depth,
                            self.windshield_h_cm - (v - h / 2.0) * depth / fy,
                        ),
                        image_center=observation.center,
                        diameter_px=observation.diameter_px,
                        confidence=observation.confidence,
                        timestamp=time.time(),
                    ))

                sources = self._source_tracker.update(candidates)
                detection_complete_ns = time.monotonic_ns()
                self.pipeline_timing.emit({
                    "stream": "road_primary",
                    "frame_index": frame_number,
                    "capture_started_ns": capture_started_ns,
                    "capture_complete_ns": capture_complete_ns,
                    "detection_complete_ns": detection_complete_ns,
                    "observation_valid": bool(sources),
                })
                if not sources:
                    if not lost_announced:
                        self.headlight_lost.emit()
                        lost_announced = True
                else:
                    lost_announced = False
                    self.lights_detected.emit(sources)
                    primary = sources[0]
                    self.headlight_detected.emit(*primary.position)
                    if processed.observations:
                        observation = processed.observations[0]
                        self.light_observed.emit(
                            observation.center[0], observation.center[1],
                            observation.diameter_px, w, h)

                preview = _preview_frame(
                    frame, processed, sources, self.preview_mode, settings)
                if self.preview_mode == "Detection overlay":
                    cv2.putText(
                        preview,
                        f"{frame.shape[1]}x{frame.shape[0]}  "
                        f"{measured_fps:.1f} FPS",
                        (8, preview.shape[0] - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44,
                        (255, 220, 80), 1, cv2.LINE_AA,
                    )
                if (brightness_90 > 245.0
                        and self.preview_mode == "Detection overlay"):
                    cv2.putText(
                        preview, "OVEREXPOSED - reduce exposure / brightness",
                        (8, preview.shape[0] - 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 80, 255), 2,
                    )
                self.frame_ready.emit(_to_qimage(preview))
        except Exception as error:
            print(f"Single-camera headlight tracking stopped: {error}", file=sys.stderr)
            self.camera_status.emit(f"Camera error: {error}", False)
            self.headlight_lost.emit()
        finally:
            _safe_release(cap)
            self._running = False


class HeadlightDetectorThread(QThread):
    """Track and triangulate multiple independent lights with a stereo pair.

    Signals
    -------
    frame_ready(QImage)
        Side-by-side composite frame for UI monitoring.
    headlight_detected(float, float, float)
        Triangulated 3D position (X, Y, Z) in cm.
    headlight_lost()
        Emitted when the light is not visible in both cameras.
    """

    frame_ready = pyqtSignal(QImage)
    stereo_frames_ready = pyqtSignal(QImage, QImage)
    stereo_diagnostics = pyqtSignal(str)
    headlight_detected = pyqtSignal(float, float, float)
    lights_detected = pyqtSignal(object)
    headlight_lost = pyqtSignal()
    camera_status = pyqtSignal(str, bool)
    camera_controls_report = pyqtSignal(object)
    background_status = pyqtSignal(str)
    pipeline_timing = pyqtSignal(object)

    def __init__(
        self, cam1_idx: int = 1, cam2_idx: int = 2,
        camera_height_cm: float = 19.5, brightness_threshold: int = 210,
        detection_settings: Optional[LightDetectionSettings] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.cam1_idx = cam1_idx
        self.cam2_idx = cam2_idx
        self.camera_height_cm = camera_height_cm
        self.detection_settings = (
            detection_settings
            or LightDetectionSettings(
                brightness_threshold=brightness_threshold)
        ).normalized()
        self.brightness_threshold = self.detection_settings.brightness_threshold
        self.preview_modes = [PREVIEW_MODES[0], PREVIEW_MODES[0]]
        self._settings_revision = 0
        self._running = False
        self._background_gray_1: Optional[np.ndarray] = None
        self._background_gray_2: Optional[np.ndarray] = None
        self._capture_background_requested = False
        self._source_tracker = LightSourceTracker(
            smoothing_alpha=0.24,
            hold_frames=4,
            match_distance_px=self.detection_settings.match_distance_px,
            max_sources=self.detection_settings.max_sources,
        )
        self._calib: Optional[StereoCalibrationResult] = None

        try:
            self._calib = load_stereo_calibration(stereo_profile_name(cam1_idx, cam2_idx))
        except Exception:
            pass

    def stop(self):
        self._running = False
        if self.isRunning():
            self.wait(5000)

    def update_detection_threshold(self, value: int):
        self.update_detection_settings(replace(
            self.detection_settings,
            brightness_threshold=int(value),
        ))

    def update_detection_settings(self, settings: LightDetectionSettings):
        self.detection_settings = settings.normalized()
        self.brightness_threshold = self.detection_settings.brightness_threshold
        self._settings_revision += 1

    def set_preview_mode(self, preview_mode: str, camera_number: int = 1):
        if preview_mode in PREVIEW_MODES and camera_number in (1, 2):
            self.preview_modes[camera_number - 1] = preview_mode

    def capture_background(self):
        self._capture_background_requested = True

    def clear_background(self):
        self._background_gray_1 = None
        self._background_gray_2 = None
        self._capture_background_requested = False
        self.background_status.emit("Stereo background references cleared")

    def run(self):  # noqa: C901
        self._running = True
        cap1, cap2 = None, None

        try:
            if self.cam1_idx == self.cam2_idx:
                raise ValueError("Stereo requires two different camera indices")
            cap1, backend1 = open_video_capture(self.cam1_idx)
            cap2, backend2 = open_video_capture(self.cam2_idx)

            if cap1 is None or cap2 is None:
                missing = []
                if cap1 is None:
                    missing.append(str(self.cam1_idx))
                if cap2 is None:
                    missing.append(str(self.cam2_idx))
                self.camera_status.emit(
                    f"Camera(s) {', '.join(missing)} not detected", False)
                self.headlight_lost.emit()
                return

            self.camera_status.emit(
                f"Cameras {self.cam1_idx} ({backend1}) + "
                f"{self.cam2_idx} ({backend2}) connected (stereo)", True)

            primary_report = None
            for camera_number, cap in enumerate((cap1, cap2), start=1):
                configure_video_capture(cap)
                report = _apply_camera_controls(
                    cap, self.detection_settings)
                if camera_number == 1:
                    primary_report = report
            self.camera_controls_report.emit(primary_report)
            applied_settings_revision = self._settings_revision

            lost_announced = False
            frame_number = 0
            last_diagnostics = 0.0
            read_failures = 0
            while self._running:
                # Sequential grabs reduce readout delay but do not synchronize exposure.
                capture_started_ns = time.monotonic_ns()
                grabbed1, grabbed2 = cap1.grab(), cap2.grab()
                if not (grabbed1 and grabbed2):
                    read_failures += 1
                    self._source_tracker.clear()
                    self.headlight_lost.emit()
                    if read_failures == 1:
                        self.stereo_diagnostics.emit("Stereo frame grab failed; output cleared")
                    if read_failures >= 30:
                        raise RuntimeError("Repeated stereo grab failures; reconnect and Run again")
                    self.msleep(30)
                    continue

                ret1, frame1 = cap1.retrieve()
                primary_capture_complete_ns = time.monotonic_ns()
                ret2, frame2 = cap2.retrieve()
                secondary_capture_complete_ns = time.monotonic_ns()
                if not (ret1 and ret2):
                    read_failures += 1
                    self._source_tracker.clear()
                    self.headlight_lost.emit()
                    if read_failures == 1:
                        self.stereo_diagnostics.emit("Stereo frame read failed; output cleared")
                    if read_failures >= 30:
                        raise RuntimeError("Repeated stereo read failures; reconnect and Run again")
                    self.msleep(30)
                    continue
                read_failures = 0
                frame_number += 1

                if applied_settings_revision != self._settings_revision:
                    reports = [
                        _apply_camera_controls(
                            capture, self.detection_settings)
                        for capture in (cap1, cap2)
                    ]
                    self.camera_controls_report.emit(reports[0])
                    self._source_tracker.configure(
                        self.detection_settings.match_distance_px,
                        self.detection_settings.max_sources,
                    )
                    applied_settings_revision = self._settings_revision

                if self._capture_background_requested:
                    self._background_gray_1 = _light_intensity(frame1)
                    self._background_gray_2 = _light_intensity(frame2)
                    self._capture_background_requested = False
                    self.background_status.emit(
                        "Stereo backgrounds captured — introduce the test light now")

                settings = self.detection_settings
                processed1 = process_bright_spots(
                    frame1, settings, self._background_gray_1)
                processed2 = process_bright_spots(
                    frame2, settings, self._background_gray_2)
                compatible = (
                    frame1.shape[:2] == frame2.shape[:2]
                    and stereo_profile_compatible(
                        self._calib, self.cam1_idx, self.cam2_idx,
                        (frame1.shape[1], frame1.shape[0])))
                if not compatible:
                    self._source_tracker.clear()
                candidates = _match_stereo_candidates(
                    processed1,
                    processed2,
                    self._calib if compatible else None,
                    frame1.shape,
                    self.camera_height_cm,
                )
                now = time.monotonic()
                if now - last_diagnostics >= 0.5:
                    prefix = ("Calibrated" if compatible else
                              "Calibration required (missing/incompatible profile); previews only")
                    self.stereo_diagnostics.emit(
                        f"{prefix} | Left: {len(processed1.observations)} | "
                        f"Right: {len(processed2.observations)} | Matches: {len(candidates)}")
                    last_diagnostics = now
                sources = self._source_tracker.update(candidates)
                detection_complete_ns = time.monotonic_ns()
                self.pipeline_timing.emit({
                    "stream": "road_stereo",
                    "frame_index": frame_number,
                    "capture_started_ns": capture_started_ns,
                    "capture_complete_ns": secondary_capture_complete_ns,
                    "primary_capture_complete_ns": primary_capture_complete_ns,
                    "secondary_capture_complete_ns": secondary_capture_complete_ns,
                    "readout_completion_skew_ns": (
                        secondary_capture_complete_ns
                        - primary_capture_complete_ns
                    ),
                    "detection_complete_ns": detection_complete_ns,
                    "observation_valid": bool(sources),
                })
                if not sources:
                    if not lost_announced:
                        self.headlight_lost.emit()
                        lost_announced = True
                else:
                    lost_announced = False
                    self.lights_detected.emit(sources)
                    self.headlight_detected.emit(*sources[0].position)

                preview1 = _preview_frame(
                    frame1,
                    processed1,
                    sources,
                    self.preview_modes[0],
                    settings,
                )
                preview2 = _preview_frame(
                    frame2,
                    processed2,
                    sources,
                    self.preview_modes[1],
                    settings,
                    secondary=True,
                )
                height, width = preview1.shape[:2]
                target_width = 320
                target_height = int(height * target_width / width)
                primary_small = cv2.resize(
                    preview1, (target_width, target_height))
                secondary_small = cv2.resize(
                    preview2, (target_width, target_height))
                self.stereo_frames_ready.emit(
                    _to_qimage(primary_small),
                    _to_qimage(secondary_small),
                )
                self.frame_ready.emit(_to_qimage(np.hstack((
                    primary_small, secondary_small,
                ))))

        except Exception as error:
            print(f"Stereo headlight tracking stopped: {error}", file=sys.stderr)
            self.camera_status.emit(f"Stereo camera error: {error}", False)
            self.headlight_lost.emit()
        finally:
            _safe_release(cap1)
            _safe_release(cap2)
            self._running = False
