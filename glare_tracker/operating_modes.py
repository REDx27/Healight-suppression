"""Explicit operating-mode and session-state policy for GlareTracker."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperatingMode(str, Enum):
    FULLY_AUTO = "Fully Auto"
    FULLY_MANUAL = "Fully Manual"
    DRIVER_FIXED = "Driver Position Fixed"
    HEADLIGHT_FIXED = "Headlight Position Fixed"


class SessionState(str, Enum):
    RUN = "Run"
    STANDBY = "Standby"
    STOP = "Stop"


@dataclass(frozen=True)
class ModePolicy:
    use_driver_camera: bool
    use_road_camera: bool
    manual_driver: bool
    manual_headlight: bool
    description: str


_POLICIES = {
    OperatingMode.FULLY_AUTO: ModePolicy(
        True, True, False, False,
        "Driver and headlight positions come from live cameras.",
    ),
    OperatingMode.FULLY_MANUAL: ModePolicy(
        False, False, True, True,
        "Enter both driver and headlight coordinates manually.",
    ),
    OperatingMode.DRIVER_FIXED: ModePolicy(
        False, True, True, False,
        "Driver position is fixed manually; road camera tracks the headlight.",
    ),
    OperatingMode.HEADLIGHT_FIXED: ModePolicy(
        True, False, False, True,
        "Driver camera tracks the eyes; headlight position is fixed manually.",
    ),
}


def policy_for(mode: OperatingMode | str) -> ModePolicy:
    """Return the input policy for *mode*."""
    if not isinstance(mode, OperatingMode):
        mode = OperatingMode(mode)
    return _POLICIES[mode]


def cameras_enabled(state: SessionState | str) -> bool:
    """Camera previews are available in Run and Standby."""
    if not isinstance(state, SessionState):
        state = SessionState(state)
    return state is not SessionState.STOP


def calculations_enabled(state: SessionState | str) -> bool:
    """Coordinate calculations are accepted only in Run."""
    if not isinstance(state, SessionState):
        state = SessionState(state)
    return state is SessionState.RUN
