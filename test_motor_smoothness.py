from motor import (
    MAX_STEPS_PER_UPDATE,
    STEPPER_MAX_STEPS_PER_SECOND,
    STEPPER_MIN_STEPS_PER_SECOND,
    STEPPER_NEAR_TARGET_STEPS,
    STEPPER_STOP_DEADBAND_STEPS,
    StepperMotorDriver,
)


class FakeStepper:
    def __init__(self) -> None:
        self.steps_calls: list[int] = []
        self.speed_rpm_calls: list[float] = []
        self._number_of_steps = 64

    def step(self, steps_to_move: int) -> None:
        self.steps_calls.append(steps_to_move)

    def set_speed_rpm(self, rpm: float) -> None:
        self.speed_rpm_calls.append(rpm)


def create_driver_with_fake_stepper() -> StepperMotorDriver:
    driver = StepperMotorDriver(initial_opening_percent=0.0)
    driver._stepper = FakeStepper()
    return driver


def test_compute_step_budget_scales_with_elapsed_time():
    driver = create_driver_with_fake_stepper()
    driver._current_speed_steps_per_second = STEPPER_MAX_STEPS_PER_SECOND

    budget = driver._compute_step_budget(0.1)
    expected = int(STEPPER_MAX_STEPS_PER_SECOND * 0.1)

    assert budget == expected


def test_compute_step_budget_is_bounded_for_short_and_long_ticks():
    driver = create_driver_with_fake_stepper()
    driver._current_speed_steps_per_second = STEPPER_MAX_STEPS_PER_SECOND

    short_tick_budget = driver._compute_step_budget(0.001)
    long_tick_budget = driver._compute_step_budget(2.0)

    assert short_tick_budget == 1
    assert long_tick_budget == MAX_STEPS_PER_UPDATE


def test_update_accelerates_and_executes_incremental_movement():
    driver = create_driver_with_fake_stepper()
    fake_stepper = driver._stepper

    driver.set_target_opening_percent(100.0)
    driver.update(0.1)

    assert fake_stepper.steps_calls == [36]
    assert driver._current_speed_steps_per_second == STEPPER_MAX_STEPS_PER_SECOND
    assert driver.get_current_opening_percent() > 0.0


def test_target_reached_uses_deadband():
    driver = create_driver_with_fake_stepper()
    driver._current_steps = 100
    target_steps_inside_deadband = 100 + STEPPER_STOP_DEADBAND_STEPS

    reached = driver._is_target_reached(target_steps_inside_deadband - driver._current_steps)

    assert reached is True


def test_target_speed_is_reduced_near_goal():
    driver = create_driver_with_fake_stepper()
    near_target_delta = STEPPER_NEAR_TARGET_STEPS

    target_speed = driver._compute_target_speed_steps_per_second(near_target_delta)

    assert target_speed == STEPPER_MIN_STEPS_PER_SECOND
