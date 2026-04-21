from __future__ import annotations

import os

import pytest

from motor import StepperMotorDriver, create_motor
from sensors import SensorManager


def _distance_readable(sensor_manager: SensorManager, attempts: int = 5) -> bool:
    """Retourne True si au moins une lecture ultrason est exploitable."""
    for _ in range(attempts):
        distance_cm = sensor_manager.read_distance_cm()
        if distance_cm is not None and 0.0 <= distance_cm <= 500.0:
            return True
    return False


@pytest.mark.skipif(
    os.getenv("RUN_HARDWARE_TESTS") != "1",
    reason="Test matériel: définir RUN_HARDWARE_TESTS=1 sur Raspberry Pi.",
)
def test_hardware_components_diagnostic() -> None:
    """
    Diagnostic matériel complet.

    Le test échoue avec un résumé explicite des composantes non fonctionnelles.
    """
    sensor_manager = SensorManager()
    if not sensor_manager.is_hardware_available:
        pytest.skip("Raspberry Pi non détecté: diagnostic matériel ignoré.")

    # Forcer une lecture pour mettre à jour les indicateurs fallback.
    _ = sensor_manager.read_temperature_c()
    _ = sensor_manager.read_luminosity_percent()

    motor = create_motor(initial_opening_percent=0.0, use_stepper_on_raspberry=True)

    adc_detected = bool(getattr(sensor_manager, "_adc_available", False))
    distance_detected = bool(getattr(sensor_manager, "_distance_available", False))
    temperature_ok = adc_detected and not sensor_manager.is_temperature_from_fallback()
    luminosity_ok = adc_detected and not sensor_manager.is_luminosity_from_fallback()
    distance_ok = distance_detected and _distance_readable(sensor_manager)
    motor_ok = isinstance(motor, StepperMotorDriver) and getattr(motor, "_stepper", None) is not None

    failures: list[str] = []
    if not adc_detected:
        failures.append("ADC non détecté (I2C 0x48/0x4B)")
    if adc_detected and not temperature_ok:
        failures.append("Capteur température indisponible (fallback actif)")
    if adc_detected and not luminosity_ok:
        failures.append("Capteur luminosité indisponible (fallback actif)")
    if not distance_detected:
        failures.append("Capteur ultrason non initialisé")
    elif not distance_ok:
        failures.append("Capteur ultrason détecté mais aucune mesure valide (no echo)")
    if not motor_ok:
        failures.append("Moteur stepper non initialisé")

    assert not failures, "Diagnostic matériel en échec: " + " | ".join(failures)
