"""Convenience re-exports for all UI widgets."""

from glare_tracker.widgets.video import VideoWidget
from glare_tracker.widgets.windshield_2d import Windshield2DWidget
from glare_tracker.widgets.scene_3d import Scene3DWidget
from glare_tracker.widgets.readout import ReadoutPanel
from glare_tracker.widgets.controls import ControlsPanel
from glare_tracker.widgets.dashboard import (
    ApplicationHeader, CameraFeedPanel, CameraPreviewCard, OperationsSidebar,
    SceneWorkspace, StatusBadge,
)

__all__ = [
    "VideoWidget",
    "Windshield2DWidget",
    "Scene3DWidget",
    "ReadoutPanel",
    "ControlsPanel",
    "ApplicationHeader",
    "CameraFeedPanel",
    "CameraPreviewCard",
    "OperationsSidebar",
    "SceneWorkspace",
    "StatusBadge",
]
