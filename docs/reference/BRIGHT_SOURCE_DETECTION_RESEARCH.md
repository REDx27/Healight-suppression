# Bright-Source Detection Research Decision

## Bench observation - 2026-11-04

The two uploaded upper-light screenshots show two candidates on both road-camera
overlays, while the application reports no paired source. This means candidate
detection succeeded and rough stereo correspondence rejected the observations. The
former rough matcher allowed a wide vertical difference for one source but a much
tighter absolute-row difference for multiple sources. With differently cropped or
tilted uncalibrated cameras, moving the same pair vertically could therefore make all
matches disappear.

The rough matcher now estimates the common vertical image offset from horizontally
ordered candidates and scores residual row error. This is suitable for detector
bring-up only. It does not estimate camera geometry or make uncalibrated depth valid.

## Selected detector architecture

For the current filtered, low-resolution USB feeds, retain and incrementally validate
the following automatic classical pipeline:

1. strongest-channel intensity so coloured emitters are not lost in grayscale;
2. multi-scale directional local contrast to enhance compact peaks while suppressing
   broad illumination;
3. a separate neutral saturated-core path for clipped white lamps;
4. adaptive thresholding plus area, compactness, edge and elongation rejection;
5. weighted-centroid candidate positions with confidence scores;
6. temporal stable IDs and brief dropout tolerance; and
7. calibrated rectification, epipolar gating and exact one-to-one stereo assignment.

This direction follows published small-target work in which local contrast enhances a
compact target and suppresses background clutter, followed by adaptive segmentation.
Weighted strengthened local contrast adds explicit target/background weighting, while
later density-peak/local-contrast work uses a candidate stage before local saliency and
adaptive thresholding. These ideas transfer well to the sunglass-filtered feed, which
behaves more like sparse bright-target imagery than ordinary textured stereo.

A trained segmentation network is not the next implementation step. The project has
no labelled, representative day/night/filter dataset, and a learned model would hide
failure causes during calibration bring-up. It can be evaluated later against the
classical pipeline after recorded data and ground truth exist.

## Calibration board decision

The supplied board uses 9 x 6 inner corners (10 x 7 printed squares) with 20.00 mm
squares on A4 landscape. At this size the complete board is 200 x 140 mm and retains
more than one square width of white space on all sides. OpenCV recommends a flat matte
target, larger image features where practical, a white surrounding border, multiple
varied views and measured physical square size. The calibration detector now tries
`findChessboardCornersSB` with exhaustive/accuracy flags before the classic
`findChessboardCorners` fallback.

## Primary sources

- Chen et al., "A Local Contrast Method for Small Infrared Target Detection," IEEE
  TGRS, 2014: https://doi.org/10.1109/TGRS.2013.2242477
- Han et al., "Infrared Small Target Detection Based on the Weighted Strengthened
  Local Contrast Measure," IEEE GRSL, 2021:
  https://doi.org/10.1109/LGRS.2020.3004978
- Li et al., "Infrared Small Target Detection Based on the Improved Density Peak
  Global Search and Human Visual Local Contrast Mechanism," IEEE JSTARS, 2022:
  https://doi.org/10.1109/JSTARS.2022.3193884
- OpenCV, `SimpleBlobDetector` reference:
  https://docs.opencv.org/4.0.1/d0/d7a/classcv_1_1SimpleBlobDetector.html
- OpenCV, calibration-pattern recommendations:
  https://docs.opencv.org/5.0/tutorials/calib3d/camera_calibration_pattern/camera_calibration_pattern.html
- OpenCV, camera calibration and `findChessboardCornersSB`:
  https://docs.opencv.org/4.4.0/d9/d0c/group__calib3d.html
