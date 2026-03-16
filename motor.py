"""
Simulation et driver réel du moteur pas-à-pas (28BYJ-48).

- MotorSimulator : pour PC ou tests sans matériel.
- StepperMotorDriver : sur Raspberry Pi, pilote le stepper via gpiozero.
  Broches par défaut (5, 6, 13, 19) pour éviter conflit avec ultrason (23, 24).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from algorithm import clamp

logger = logging.getLogger(__name__)

# Broches moteur pas-à-pas (éviter 23, 24 réservées à l'ultrason)
DEFAULT_STEPPER_PINS: Tuple[int, ...] = (18, 23, 21, 25)

# Pas total pour un cycle 0 % → 100 % (course de la porte)
STEPS_FULL_TRAVEL = 2048
# Vitesse rapide pour 28BYJ-48 avec courroie
STEPPER_MIN_STEPS_PER_SECOND = 80.0
STEPPER_MAX_STEPS_PER_SECOND = 220.0
STEPPER_ACCELERATION_STEPS_PER_SECOND2 = 400.0
STEPPER_NEAR_TARGET_STEPS = 100
STEPPER_STOP_DEADBAND_STEPS = 2
# Pas par update : pas trop d’un coup pour ne pas décrocher
MAX_STEPS_PER_UPDATE = 80
# Vitesse affichée (tour/min) quand le moteur tourne
MOTOR_DISPLAY_RPM = 20


@dataclass(frozen=True)
class MotorStatus:
    is_running: bool
    direction_label: str  # "Gauche" / "Droite"
    speed_rpm: int


class MotorSimulator:
    """
    Simulation simple du moteur + position.

    - On suit une consigne (%) et on se déplace vers la cible avec une vitesse fixe.
    - La direction est libellée Gauche/Droite comme dans le sujet.
    """

    def __init__(
        self,
        initial_opening_percent: float = 0.0,
        movement_speed_percent_per_sec: float = 12.0,
        max_distance_cm: float = 60.0,
    ) -> None:
        self._current_opening = clamp(initial_opening_percent, 0.0, 100.0)
        self._target_opening = self._current_opening
        self._speed_percent_per_sec = max(0.1, movement_speed_percent_per_sec)
        self._max_distance_cm = max(1.0, max_distance_cm)

        self._last_motor_status = MotorStatus(is_running=False, direction_label="Droite", speed_rpm=0)

    def set_target_opening_percent(self, target_opening_percent: float) -> None:
        self._target_opening = clamp(target_opening_percent, 0.0, 100.0)

    def get_current_opening_percent(self) -> float:
        return self._current_opening

    def get_target_opening_percent(self) -> float:
        return self._target_opening

    def update(self, dt_seconds: float) -> None:
        dt = max(0.0, float(dt_seconds))
        if dt <= 1e-9:
            return

        delta = self._target_opening - self._current_opening
        if abs(delta) < 0.01:
            self._current_opening = self._target_opening
            self._last_motor_status = MotorStatus(
                is_running=False,
                direction_label=self._last_motor_status.direction_label,
                speed_rpm=0,
            )
            logger.info(
                "MotorSimulator à l'arrêt — ouverture actuelle=%.1f%% (cible=%.1f%%), dernière direction=%s",
                self._current_opening,
                self._target_opening,
                self._last_motor_status.direction_label,
            )
            return

        step = self._speed_percent_per_sec * dt
        move = clamp(delta, -step, step)
        self._current_opening = clamp(self._current_opening + move, 0.0, 100.0)

        direction = "Droite" if move > 0 else "Gauche"
        speed_rpm = 20  # valeur fixe de démo, comme l'exemple du sujet
        self._last_motor_status = MotorStatus(is_running=True, direction_label=direction, speed_rpm=speed_rpm)
        logger.info(
            "MotorSimulator en mouvement — direction=%s, ouverture actuelle=%.1f%%, cible=%.1f%%, delta=%.2f%%",
            direction,
            self._current_opening,
            self._target_opening,
            delta,
        )

    def get_motor_status(self) -> MotorStatus:
        return self._last_motor_status

    def get_distance_cm(self) -> float:
        # Interprétation simple : "hauteur d'ouverture" proportionnelle au % (0..max_distance_cm)
        return (self._current_opening / 100.0) * self._max_distance_cm


def _create_stepper_output_devices(pins: Tuple[int, ...]) -> Optional[List[Any]]:
    """Crée les OutputDevice gpiozero pour les broches du stepper. Retourne None si échec."""
    try:
        from gpiozero import OutputDevice
        return [OutputDevice(pin) for pin in pins]
    except Exception as e:
        logger.warning("Stepper (gpiozero): impossible de créer les sorties: %s", e)
        return None


class _InlineStepper:
    """
    Moteur pas-à-pas 4 phases (style 28BYJ-48), même logique que Freenove gpiostepper.
    Séquence demi-pas (8 phases) pour un mouvement plus fluide.
    """

    def __init__(self, motor_pins: List[Any], number_of_steps: int = 64) -> None:
        self._pins = motor_pins
        self._pin_count = len(motor_pins)
        self._step_sequence = [
            [1, 0, 0, 0],
            [1, 1, 0, 0],
            [0, 1, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 1, 0],
            [0, 0, 1, 1],
            [0, 0, 0, 1],
            [1, 0, 0, 1],
        ]
        self._step_number = 0
        self._number_of_steps = number_of_steps
        rpm = 120.0
        self._step_delay = 60.0 / (self._number_of_steps * rpm) if rpm > 0 else 0.008
        self._min_step_delay_s = 0.0012

    def set_speed_rpm(self, rpm: float) -> None:
        if rpm <= 0:
            return
        delay = 60.0 / (self._number_of_steps * rpm)
        self._step_delay = max(delay, self._min_step_delay_s)

    def step(self, steps_to_move: int) -> None:
        """Exécute steps_to_move pas (négatif = sens inverse)."""
        steps_left = abs(steps_to_move)
        direction = 1 if steps_to_move >= 0 else -1
        while steps_left > 0:
            self._step_number = (self._step_number + direction) % self._number_of_steps
            self._do_one_step()
            steps_left -= 1

    def _do_one_step(self) -> None:
        idx = self._step_number % len(self._step_sequence)
        seq = self._step_sequence[idx]
        for i in range(self._pin_count):
            if seq[i] == 1:
                self._pins[i].on()
            else:
                self._pins[i].off()
        time.sleep(max(self._step_delay, self._min_step_delay_s))

    def close(self) -> None:
        for p in self._pins:
            try:
                p.close()
            except Exception:
                pass


class StepperMotorDriver:
    """
    Driver moteur pas-à-pas (28BYJ-48) avec la même interface que MotorSimulator.

    Broches par défaut (5, 6, 13, 19) pour ne pas utiliser 23, 24 (ultrason).
    """

    def __init__(
        self,
        initial_opening_percent: float = 0.0,
        motor_pins: Optional[Tuple[int, ...]] = None,
        max_distance_cm: float = 60.0,
    ) -> None:
        pins = motor_pins or DEFAULT_STEPPER_PINS
        if len(pins) != 4:
            raise ValueError("Le moteur pas-à-pas nécessite exactement 4 broches.")
        self._max_distance_cm = max(1.0, max_distance_cm)
        self._target_opening = clamp(initial_opening_percent, 0.0, 100.0)
        self._current_opening = self._target_opening
        self._last_motor_status = MotorStatus(
            is_running=False, direction_label="Droite", speed_rpm=0
        )
        self._stepper: Optional[_InlineStepper] = None
        # Position en pas (0 = 0 %, STEPS_FULL_TRAVEL = 100 %)
        self._current_steps = int((self._current_opening / 100.0) * STEPS_FULL_TRAVEL)
        self._current_speed_steps_per_second = STEPPER_MIN_STEPS_PER_SECOND

        devices = _create_stepper_output_devices(pins)
        if devices is not None:
            self._stepper = _InlineStepper(devices)
            self._stepper.set_speed_rpm(self._compute_stepper_rpm())
            logger.info(
                "StepperMotorDriver initialisé — broches %s, pas total %s",
                pins,
                STEPS_FULL_TRAVEL,
            )
        else:
            logger.warning("StepperMotorDriver: gpiozero indisponible, moteur inactif.")

    def set_target_opening_percent(self, target_opening_percent: float) -> None:
        self._target_opening = clamp(target_opening_percent, 0.0, 100.0)

    def get_current_opening_percent(self) -> float:
        return self._current_opening

    def get_target_opening_percent(self) -> float:
        return self._target_opening

    def update(self, dt_seconds: float) -> None:
        dt = self._normalize_dt(dt_seconds)
        if not self._is_update_allowed(dt):
            return

        target_steps = self._convert_opening_percent_to_steps(self._target_opening)
        delta_steps = target_steps - self._current_steps
        if self._is_target_reached(delta_steps):
            self._sync_at_target_position(target_steps)
            return

        self._adapt_stepper_speed(dt, delta_steps)
        steps_budget = self._compute_step_budget(dt)
        steps_to_do = self._compute_steps_to_execute(delta_steps, steps_budget)
        if steps_to_do == 0:
            self._mark_motor_running_without_step(delta_steps)
            return

        self._stepper.step(steps_to_do)
        self._apply_executed_steps(steps_to_do)
        self._update_running_motor_status(steps_to_do)
        self._log_movement(steps_to_do)

    def _normalize_dt(self, dt_seconds: float) -> float:
        return max(0.0, float(dt_seconds))

    def _is_update_allowed(self, dt: float) -> bool:
        return dt > 1e-9 and self._stepper is not None

    def _convert_opening_percent_to_steps(self, opening_percent: float) -> int:
        return int((opening_percent / 100.0) * STEPS_FULL_TRAVEL)

    def _is_target_reached(self, delta_steps: int) -> bool:
        return abs(delta_steps) <= STEPPER_STOP_DEADBAND_STEPS

    def _sync_at_target_position(self, target_steps: int) -> None:
        self._current_steps = int(clamp(target_steps, 0, STEPS_FULL_TRAVEL))
        self._current_opening = (self._current_steps / STEPS_FULL_TRAVEL) * 100.0
        self._last_motor_status = MotorStatus(
            is_running=False,
            direction_label=self._last_motor_status.direction_label,
            speed_rpm=0,
        )
        logger.info(
            "StepperMotorDriver à l'arrêt — pas actuels=%d (ouverture=%.1f%%, cible=%.1f%%), dernière direction=%s",
            self._current_steps,
            self._current_opening,
            self._target_opening,
            self._last_motor_status.direction_label,
        )

    def _adapt_stepper_speed(self, dt: float, delta_steps: int) -> None:
        target_speed = self._compute_target_speed_steps_per_second(delta_steps)
        self._current_speed_steps_per_second = self._compute_next_speed_steps_per_second(dt, target_speed)
        self._stepper.set_speed_rpm(self._compute_stepper_rpm())

    def _compute_target_speed_steps_per_second(self, delta_steps: int) -> float:
        if abs(delta_steps) <= STEPPER_NEAR_TARGET_STEPS:
            return STEPPER_MIN_STEPS_PER_SECOND
        return STEPPER_MAX_STEPS_PER_SECOND

    def _compute_next_speed_steps_per_second(self, dt: float, target_speed: float) -> float:
        max_speed_delta = STEPPER_ACCELERATION_STEPS_PER_SECOND2 * dt
        speed_error = target_speed - self._current_speed_steps_per_second
        clamped_delta = clamp(speed_error, -max_speed_delta, max_speed_delta)
        new_speed = self._current_speed_steps_per_second + clamped_delta
        return float(clamp(new_speed, STEPPER_MIN_STEPS_PER_SECOND, STEPPER_MAX_STEPS_PER_SECOND))

    def _compute_step_budget(self, dt: float) -> int:
        unclamped_budget = int(self._current_speed_steps_per_second * dt)
        return int(clamp(unclamped_budget, 1, MAX_STEPS_PER_UPDATE))

    def _compute_steps_to_execute(self, delta_steps: int, step_budget: int) -> int:
        return int(clamp(delta_steps, -step_budget, step_budget))

    def _mark_motor_running_without_step(self, delta_steps: int) -> None:
        direction_label = "Droite" if delta_steps > 0 else "Gauche"
        self._last_motor_status = MotorStatus(
            is_running=True,
            direction_label=direction_label,
            speed_rpm=MOTOR_DISPLAY_RPM,
        )

    def _apply_executed_steps(self, steps_to_do: int) -> None:
        self._current_steps += steps_to_do
        self._current_steps = int(clamp(self._current_steps, 0, STEPS_FULL_TRAVEL))
        self._current_opening = (self._current_steps / STEPS_FULL_TRAVEL) * 100.0

    def _update_running_motor_status(self, steps_to_do: int) -> None:
        direction_label = "Droite" if steps_to_do > 0 else "Gauche"
        self._last_motor_status = MotorStatus(
            is_running=True,
            direction_label=direction_label,
            speed_rpm=MOTOR_DISPLAY_RPM,
        )

    def _log_movement(self, steps_to_do: int) -> None:
        direction_label = self._last_motor_status.direction_label
        logger.info(
            "StepperMotorDriver en mouvement — direction=%s, pas effectués=%d, pas actuels=%d, ouverture=%.1f%%, cible=%.1f%%",
            direction_label,
            steps_to_do,
            self._current_steps,
            self._current_opening,
            self._target_opening,
        )

    def _compute_stepper_rpm(self) -> float:
        if self._stepper is None:
            return 0.0
        return (self._current_speed_steps_per_second * 60.0) / float(self._stepper._number_of_steps)

    def get_motor_status(self) -> MotorStatus:
        return self._last_motor_status

    def get_distance_cm(self) -> float:
        return (self._current_opening / 100.0) * self._max_distance_cm


def create_motor(
    initial_opening_percent: float = 0.0,
    use_stepper_on_raspberry: bool = True,
    stepper_pins: Optional[Tuple[int, ...]] = None,
) -> Any:
    """
    Crée le moteur à utiliser : StepperMotorDriver sur RPi si gpio disponible,
    sinon MotorSimulator (PC ou échec d'init stepper).
    """
    try:
        import RPi.GPIO  # noqa: F401
    except Exception:
        return MotorSimulator(initial_opening_percent=initial_opening_percent)

    if not use_stepper_on_raspberry:
        return MotorSimulator(initial_opening_percent=initial_opening_percent)

    try:
        driver = StepperMotorDriver(
            initial_opening_percent=initial_opening_percent,
            motor_pins=stepper_pins,
        )
        if driver._stepper is not None:
            return driver
    except Exception as e:
        logger.warning("StepperMotorDriver non disponible, utilisation du simulateur: %s", e)
    return MotorSimulator(initial_opening_percent=initial_opening_percent)

