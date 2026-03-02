"""
Simulation du moteur et du capteur de distance.
"""

from __future__ import annotations

from dataclasses import dataclass

from algorithm import clamp


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
            return

        step = self._speed_percent_per_sec * dt
        move = clamp(delta, -step, step)
        self._current_opening = clamp(self._current_opening + move, 0.0, 100.0)

        direction = "Droite" if move > 0 else "Gauche"
        speed_rpm = 20  # valeur fixe de démo, comme l'exemple du sujet
        self._last_motor_status = MotorStatus(is_running=True, direction_label=direction, speed_rpm=speed_rpm)

    def get_motor_status(self) -> MotorStatus:
        return self._last_motor_status

    def get_distance_cm(self) -> float:
        # Interprétation simple : "hauteur d'ouverture" proportionnelle au % (0..max_distance_cm)
        return (self._current_opening / 100.0) * self._max_distance_cm

