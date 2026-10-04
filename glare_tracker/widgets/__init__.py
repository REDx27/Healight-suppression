"""Convenience re-exports for all UI widgets."""

from glare_tracker.widgets.video import VideoWidget
from glare_tracker.widgets.windshield_2d import Windshield2DWidget
from glare_tracker.widgets.scene_3d import Scene3DWidget
from glare_tracker.widgets.readout import ReadoutPanel
from glare_tracker.widgets.controls import ControlsPanel
from glare_tracker.widgets.calibration_wizard import GuidedCalibrationWizard
from glare_tracker.widgets.dashboard import (
    ApplicationHeader, CameraFeedPanel, CameraPreviewCard, ConfigurationSidebar,
    OperationsSidebar, SceneWorkspace, StatusBadge,
)
from glare_tracker.widgets.icons import ICON_SIZE, IconFactory

__all__ = [
    "VideoWidget",
    "Windshield2DWidget",
    "Scene3DWidget",
    "ReadoutPanel",
    "ControlsPanel",
    "GuidedCalibrationWizard",
    "ApplicationHeader",
    "CameraFeedPanel",
    "CameraPreviewCard",
    "ConfigurationSidebar",
    "OperationsSidebar",
    "SceneWorkspace",
    "StatusBadge",
    "IconFactory",
    "ICON_SIZE",
]
