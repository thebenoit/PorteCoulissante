"""
Gestion des capteurs réels ou simulés.

Sur PC (sans Raspberry Pi), les valeurs sont simulées via un random walk
pour obtenir des évolutions réalistes de température et de luminosité.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from algorithm import clamp


class RandomWalkSignal:
    """Générateur simple de signaux réalistes (variation progressive) pour la simulation."""

    def __init__(self, initial: float, low: float, high: float, max_step: float) -> None:
        self._value = initial
        self._low = low
        self._high = high
        self._max_step = max_step

    def next_value(self) -> float:
        self._value += random.uniform(-self._max_step, self._max_step)
        self._value = clamp(self._value, self._low, self._high)
        return self._value


class SensorManager:
    """
    Gestionnaire de capteurs.

    - Sur Raspberry Pi : la classe est prête à être étendue pour utiliser RPi.GPIO et les capteurs réels.
    - Sur PC : retour de valeurs simulées (random walk) pour la démonstration.
    """

    def __init__(self) -> None:
        self.is_hardware_available = self._detect_raspberry_gpio()

        # Simulation : signaux "lents" (plus crédibles que du random brut)
        self._sim_temperature = RandomWalkSignal(initial=30.0, low=0.0, high=50.0, max_step=1.2)
        self._sim_luminosity = RandomWalkSignal(initial=80.0, low=0.0, high=100.0, max_step=3.5)

    def _detect_raspberry_gpio(self) -> bool:
        try:
            import RPi.GPIO as _  # noqa: F401  (utilisé seulement pour détecter)

            return True
        except Exception:
       	    return False

    def read_temperature_c(self) -> float:
        if self.is_hardware_available:
            return self._read_temperature_from_dht11()
        return float(self._sim_temperature.next_value())

    def read_luminosity_percent(self) -> float:
        if self.is_hardware_available:
            return self._read_luminosity_from_photoresistor()
        return float(self._sim_luminosity.next_value())

    # ---- Capteurs réels (stubs / à compléter sur Raspberry Pi) ----

    def _read_temperature_from_dht11(self) -> float:
        # Placeholder : à remplacer par une lecture réelle (DHT11/DHT22 selon votre montage).
        # Contrainte : en mode simulation PC, cette méthode n'est jamais appelée.
        raise NotImplementedError("Lecture DHT11 non implémentée (prévue pour Raspberry Pi).")

    def _read_luminosity_from_photoresistor(self) -> float:
        raise NotImplementedError("Lecture photorésistance non implémentée (prévue pour Raspberry Pi).")


@dataclass(frozen=True)
class SensorReadings:
    temperature_c: float
    luminosity_percent: float

