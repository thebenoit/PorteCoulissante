from motor import (
    MAX_STEPS_PER_UPDATE,
    MIN_STEP_BUDGET_PER_UPDATE,
    STEPPER_TARGET_STEPS_PER_SECOND,
    StepperMotorDriver,
)


class FakeStepper:
    def __init__(self) -> None:
        self.steps_calls: list[int] = []

    def step(self, steps_to_move: int) -> None:
        self.steps_calls.append(steps_to_move)


def create_driver_with_fake_stepper() -> StepperMotorDriver:
    driver = StepperMotorDriver(initial_opening_percent=0.0)
    driver._stepper = FakeStepper()
    return driver


def test_compute_step_budget_scales_with_elapsed_time():
    driver = create_driver_with_fake_stepper()

    budget = driver._compute_step_budget(0.1)
    expected = int(STEPPER_TARGET_STEPS_PER_SECOND * 0.1)

    assert budget == expected


def test_compute_step_budget_is_bounded_for_short_and_long_ticks():
    driver = create_driver_with_fake_stepper()

    short_tick_budget = driver._compute_step_budget(0.001)
    long_tick_budget = driver._compute_step_budget(2.0)

    assert short_tick_budget == MIN_STEP_BUDGET_PER_UPDATE
    assert long_tick_budget == MAX_STEPS_PER_UPDATE


def test_update_executes_small_incremental_movement():
    driver = create_driver_with_fake_stepper()
    fake_stepper = driver._stepper

    driver.set_target_opening_percent(100.0)
    driver.update(0.1)

    assert fake_stepper.steps_calls == [12]
    assert driver.get_current_opening_percent() > 0.0
