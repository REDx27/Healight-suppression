"""Regression tests for operating-mode and session-state policy."""

import pytest

from glare_tracker.operating_modes import (
    OperatingMode,
    SessionState,
    calculations_enabled,
    cameras_enabled,
    policy_for,
)


@pytest.mark.parametrize(
    ("mode", "driver_camera", "road_camera", "manual_driver", "manual_light"),
    [
        (OperatingMode.FULLY_AUTO, True, True, False, False),
        (OperatingMode.FULLY_MANUAL, False, False, True, True),
        (OperatingMode.DRIVER_FIXED, False, True, True, False),
        (OperatingMode.HEADLIGHT_FIXED, True, False, False, True),
    ],
)
def test_operating_mode_source_policy(
    mode, driver_camera, road_camera, manual_driver, manual_light,
):
    policy = policy_for(mode)
    assert policy.use_driver_camera is driver_camera
    assert policy.use_road_camera is road_camera
    assert policy.manual_driver is manual_driver
    assert policy.manual_headlight is manual_light


def test_session_state_policy():
    assert cameras_enabled(SessionState.RUN)
    assert calculations_enabled(SessionState.RUN)
    assert cameras_enabled(SessionState.STANDBY)
    assert not calculations_enabled(SessionState.STANDBY)
    assert not cameras_enabled(SessionState.STOP)
    assert not calculations_enabled(SessionState.STOP)
