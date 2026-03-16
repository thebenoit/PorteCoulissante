from __future__ import annotations

import math

from controller import GreenhouseController
from motor import MOTOR_DISPLAY_RPM, MotorSimulator


class FakeSensorManager:
    def __init__(self, temperature_c: float, luminosity_percent: float) -> None:
        self._temperature_c = temperature_c
        self._luminosity_percent = luminosity_percent

    def read_temperature_c(self) -> float:
        return self._temperature_c

    def read_luminosity_percent(self) -> float:
        return self._luminosity_percent

    def read_distance_cm(self):  # type: ignore[no-untyped-def]
        return None

    def get_warnings(self) -> list[str]:
        return []

    def is_temperature_from_fallback(self) -> bool:
        return False

    def is_luminosity_from_fallback(self) -> bool:
        return False


def test_manual_target_moves_motor_toward_requested_percentage() -> None:
    sensors = FakeSensorManager(temperature_c=30.0, luminosity_percent=80.0)
    motor = MotorSimulator(initial_opening_percent=0.0)
    controller = GreenhouseController(sensor_manager=sensors, motor=motor)
    controller.set_mode("manual")
    controller.set_manual_target_opening_percent(56.0)

    snapshot = controller.step_once(dt_seconds=1.0)

    assert math.isclose(snapshot.target_opening_percent, 56.0, rel_tol=1e-6, abs_tol=1e-6)
    assert 0.0 < snapshot.current_opening_percent <= 56.0


def test_automatic_mode_uses_computed_non_zero_target_when_conditions_require_opening() -> None:
    sensors = FakeSensorManager(temperature_c=30.0, luminosity_percent=80.0)
    motor = MotorSimulator(initial_opening_percent=0.0)
    controller = GreenhouseController(sensor_manager=sensors, motor=motor)
    controller.set_mode("auto")

    snapshot = controller.step_once(dt_seconds=1.0)

    assert snapshot.automatic_opening_percent > 0.0
    assert snapshot.target_opening_percent == snapshot.automatic_opening_percent


def test_motor_running_speed_matches_configured_display_constant() -> None:
    motor = MotorSimulator(initial_opening_percent=0.0)
    motor.set_target_opening_percent(100.0)
    motor.update(dt_seconds=1.0)

    status = motor.get_motor_status()
    assert status.is_running is True
    assert status.speed_rpm == MOTOR_DISPLAY_RPM
