"""
Contrôleur principal : lit les capteurs, applique l'algorithme et pilote le moteur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from algorithm import DoorOpeningAlgorithm, clamp
from motor import MotorSimulator, MotorStatus, StepperMotorDriver
from sensors import (
    CLOSED_DISTANCE_CM,
    OPEN_DISTANCE_CM,
    SensorManager,
    SensorReadings,
    compute_door_position_from_distance,
    compute_opening_percent_from_distance,
)

MotorType = Union[MotorSimulator, StepperMotorDriver]


@dataclass(frozen=True)
class SystemSnapshot:
    readings: SensorReadings
    automatic_opening_percent: float
    target_opening_percent: float
    current_opening_percent: float
    motor_status: MotorStatus
    distance_cm: float
    door_position_normalized: float
    warnings: tuple[str, ...]


class GreenhouseController:
    """Orchestration : capteurs -> calcul -> consigne moteur, sans dépendance à l'UI."""

    def __init__(self, sensor_manager: SensorManager, motor: MotorType) -> None:
        self._sensor_manager = sensor_manager
        self._motor = motor
        self._mode = "auto"  # "auto" | "manual"
        self._manual_target_opening = 0.0

        self._last_snapshot: Optional[SystemSnapshot] = None

    def set_mode(self, mode: str) -> None:
        self._mode = "manual" if mode == "manual" else "auto"

    def get_mode(self) -> str:
        return self._mode

    def set_manual_target_opening_percent(self, opening_percent: float) -> None:
        self._manual_target_opening = clamp(opening_percent, 0.0, 100.0)

    def set_target_fully_open(self) -> None:
        self.set_manual_target_opening_percent(100.0)

    def set_target_fully_closed(self) -> None:
        self.set_manual_target_opening_percent(0.0)

    def _effective_manual_target_with_distance(
        self, real_distance_cm: float, current_opening_percent: float
    ) -> float:
        """
        En mode manuel, pour « Ouvrir » (100 %) ou « Fermer » (0 %), utilise le capteur
        de distance pour arrêter le moteur : fermé à 4 cm, ouvert à 9 cm.
        """
        if self._manual_target_opening <= 0.0:
            if real_distance_cm <= CLOSED_DISTANCE_CM:
                return current_opening_percent
            return 0.0
        if self._manual_target_opening >= 100.0:
            if real_distance_cm >= OPEN_DISTANCE_CM:
                return current_opening_percent
            return 100.0
        return self._manual_target_opening

    def step_once(self, dt_seconds: float = 1.0) -> SystemSnapshot:
        temp_c = self._sensor_manager.read_temperature_c()
        lum = self._sensor_manager.read_luminosity_percent()
        real_distance_cm = self._sensor_manager.read_distance_cm()

        # Synchroniser la position interne du moteur sur le capteur de distance pour éviter
        # que le moteur croie être à 100 % (2048 pas) alors que la porte est à 7 cm.
        if real_distance_cm is not None:
            self._motor.sync_position_from_opening_percent(
                compute_opening_percent_from_distance(real_distance_cm)
            )

        automatic_opening = DoorOpeningAlgorithm.calculate_automatic_opening_percent(
            temp_c, lum
        )
        if self._mode == "auto":
            target_opening = automatic_opening
        else:
            current_opening = (
                compute_opening_percent_from_distance(real_distance_cm)
                if real_distance_cm is not None
                else self._motor.get_current_opening_percent()
            )
            if real_distance_cm is not None:
                target_opening = self._effective_manual_target_with_distance(
                    real_distance_cm, current_opening
                )
            else:
                target_opening = self._manual_target_opening

        self._motor.set_target_opening_percent(target_opening)
        self._motor.update(dt_seconds)

        distance_cm = (
            real_distance_cm
            if real_distance_cm is not None
            else self._motor.get_distance_cm()
        )
        door_position_normalized = compute_door_position_from_distance(distance_cm)
        # Ouverture affichée = UNIQUEMENT depuis le capteur (4 cm → 0 %, 9 cm → 100 %).
        # Si pas de capteur, repli sur la position moteur.
        if real_distance_cm is not None:
            current_opening_percent = compute_opening_percent_from_distance(real_distance_cm)
        else:
            current_opening_percent = self._motor.get_current_opening_percent()
        warnings = tuple(self._sensor_manager.get_warnings())

        snapshot = SystemSnapshot(
            readings=SensorReadings(
                temperature_c=temp_c,
                luminosity_percent=lum,
                temperature_sensor_detected=not self._sensor_manager.is_temperature_from_fallback(),
                luminosity_sensor_detected=not self._sensor_manager.is_luminosity_from_fallback(),
            ),
            automatic_opening_percent=automatic_opening,
            target_opening_percent=target_opening,
            current_opening_percent=current_opening_percent,
            motor_status=self._motor.get_motor_status(),
            distance_cm=distance_cm,
            door_position_normalized=door_position_normalized,
            warnings=warnings,
        )
        self._last_snapshot = snapshot
        return snapshot

    def get_last_snapshot(self) -> Optional[SystemSnapshot]:
        return self._last_snapshot
