"""
Gestion des capteurs réels ou simulés.

Sur PC (sans Raspberry Pi), les valeurs sont simulées via un random walk.
Sur Raspberry Pi : thermistance (ADC canal 0), photorésistance (ADC canal 1),
capteur ultrason (distance). Fallback et avertissements si un capteur est absent.
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass
from typing import List, Optional, Any

from algorithm import clamp

# Délai (s) après une lecture "poubelle" pour laisser le PCF8591 terminer
# la conversion du canal luminosité (évite de lire le canal température à la place).
_PCF8591_CHANNEL_SETTLING_S = 0.005

logger = logging.getLogger(__name__)

# Valeurs de repli quand un capteur n'est pas détecté ou invalide
FALLBACK_TEMPERATURE_C = 25.0
FALLBACK_LUMINOSITY_PERCENT = 50.0

# Canaux ADC (Thermometer = canal 0, Nightlamp-style luminosité = canal 1)
ADC_CHANNEL_THERMISTOR = 0
ADC_CHANNEL_PHOTORESISTOR = 1

# Broches ultrason (ultrasonic_ex.py)
ULTRASONIC_TRIGGER_PIN = 23
ULTRASONIC_ECHO_PIN = 24
ULTRASONIC_MAX_DISTANCE_M = 3.0


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


def _convert_thermistor_adc_to_celsius(value: int) -> Optional[float]:
    """
    Convertit une lecture ADC (0-255) en °C via la formule Thermometer (thermistance).
    Retourne None si la valeur est invalide (division par zéro, voltage hors plage).
    """
    if value <= 0 or value >= 255:
        return None
    voltage = value / 255.0 * 3.3
    if voltage >= 3.3 - 1e-6:
        return None
    resistance_thermistor = 10.0 * voltage / (3.3 - voltage)
    if resistance_thermistor <= 0:
        return None
    try:
        temp_k = 1.0 / (
            1.0 / (273.15 + 25.0)
            + math.log(resistance_thermistor / 10.0) / 3950.0
        )
    except (ValueError, ZeroDivisionError):
        return None
    return temp_k - 273.15


class SensorManager:
    """
    Gestionnaire de capteurs.

    - Sur Raspberry Pi : ADC (thermistor + photorésistance), capteur ultrason.
      Fallback + avertissements si un capteur n'est pas connecté ou détecté.
    - Sur PC : valeurs simulées (random walk).
    """

    def __init__(self) -> None:
        self.is_hardware_available = self._detect_raspberry_gpio()

        # Simulation (PC)
        self._sim_temperature = RandomWalkSignal(initial=30.0, low=0.0, high=50.0, max_step=1.2)
        self._sim_luminosity = RandomWalkSignal(initial=80.0, low=0.0, high=100.0, max_step=3.5)

        # Matériel (RPi) : initialisation lazy
        self._adc: Any = None
        self._adc_available = False
        self._distance_sensor: Any = None
        self._distance_available = False
        self._temperature_fallback_used = False
        self._luminosity_fallback_used = False

        if self.is_hardware_available:
            self._init_hardware()

    def _detect_raspberry_gpio(self) -> bool:
        try:
            import RPi.GPIO as _  # noqa: F401
            logger.info("Raspberry Pi détecté (RPi.GPIO disponible).")
            return True
        except Exception as e:
            logger.info(
                "Raspberry Pi non détecté (mode simulation PC): %s",
                e,
            )
            return False

    def _init_hardware(self) -> None:
        """Initialise l'ADC et le capteur de distance lorsque le matériel est disponible."""
        self._init_adc()
        self._init_distance_sensor()
        self._log_sensor_status()

    def _init_adc(self) -> None:
        try:
            from ADCService import ADCDevice, PCF8591, ADS7830
            adc = ADCDevice()
            if adc.detectI2C(0x48):
                self._adc = PCF8591()
                self._adc_available = True
                logger.info("Capteur ADC détecté: PCF8591 (0x48) — température et luminosité disponibles.")
            elif adc.detectI2C(0x4B):
                self._adc = ADS7830()
                self._adc_available = True
                logger.info("Capteur ADC détecté: ADS7830 (0x4B) — température et luminosité disponibles.")
            else:
                self._adc = None
                self._adc_available = False
                logger.warning("Aucun ADC détecté (ni 0x48 ni 0x4B). Température et luminosité en valeur de repli.")
        except Exception as e:
            self._adc = None
            self._adc_available = False
            logger.warning("ADC non initialisable: %s — température et luminosité en valeur de repli.", e)

    def _init_distance_sensor(self) -> None:
        try:
            from gpiozero import DistanceSensor
            self._distance_sensor = DistanceSensor(
                echo=ULTRASONIC_ECHO_PIN,
                trigger=ULTRASONIC_TRIGGER_PIN,
                max_distance=ULTRASONIC_MAX_DISTANCE_M,
            )
            self._distance_available = True
            logger.info(
                "Capteur de distance (ultrason) détecté — broches trigger=%s, echo=%s.",
                ULTRASONIC_TRIGGER_PIN,
                ULTRASONIC_ECHO_PIN,
            )
        except Exception as e:
            self._distance_sensor = None
            self._distance_available = False
            logger.warning(
                "Capteur de distance (ultrason) non détecté: %s — distance simulée par le moteur.",
                e,
            )

    def _log_sensor_status(self) -> None:
        """Résumé du statut des capteurs dans les logs."""
        if not self.is_hardware_available:
            return
        temp_ok = self._adc_available
        lum_ok = self._adc_available
        dist_ok = self._distance_available
        logger.info(
            "Statut capteurs — Température: %s, Luminosité: %s, Distance: %s",
            "détecté" if temp_ok else "non détecté (repli)",
            "détecté" if lum_ok else "non détecté (repli)",
            "détecté" if dist_ok else "non détecté (repli)",
        )

    def read_temperature_c(self) -> float:
        if not self.is_hardware_available:
            return float(self._sim_temperature.next_value())

        self._temperature_fallback_used = False
        if not self._adc_available or self._adc is None:
            self._temperature_fallback_used = True
            return FALLBACK_TEMPERATURE_C

        try:
            value = self._adc.analogRead(ADC_CHANNEL_THERMISTOR)
            temp_c = _convert_thermistor_adc_to_celsius(value)
            if temp_c is None:
                self._temperature_fallback_used = True
                return FALLBACK_TEMPERATURE_C
            result = clamp(temp_c, 0.0, 50.0)
            return float(result)
        except Exception:
            self._temperature_fallback_used = True
            return FALLBACK_TEMPERATURE_C

    def _read_luminosity_adc_fresh(self) -> int:
        """
        Lit le canal ADC luminosité en s'assurant d'avoir une conversion à jour.

        Sur PCF8591, après une lecture température (canal 0), la première lecture
        du canal 1 peut renvoyer la valeur du canal 0 si la conversion n'est pas
        terminée. Une lecture poubelle + court délai + seconde lecture évite ce
        mélange de canaux (luminosité qui retombe vers 40–50 %).
        """
        self._adc.analogRead(ADC_CHANNEL_PHOTORESISTOR)
        time.sleep(_PCF8591_CHANNEL_SETTLING_S)
        return self._adc.analogRead(ADC_CHANNEL_PHOTORESISTOR)

    def read_luminosity_percent(self) -> float:
        if not self.is_hardware_available:
            return float(self._sim_luminosity.next_value())

        self._luminosity_fallback_used = False
        if not self._adc_available or self._adc is None:
            self._luminosity_fallback_used = True
            return FALLBACK_LUMINOSITY_PERCENT

        try:
            value = self._read_luminosity_adc_fresh()
            result = clamp(value / 255.0 * 100.0, 0.0, 100.0)
            return float(result)
        except Exception:
            self._luminosity_fallback_used = True
            return FALLBACK_LUMINOSITY_PERCENT

    def read_distance_cm(self) -> Optional[float]:
        """Retourne la distance en cm si le capteur ultrason est disponible, sinon None."""
        if not self.is_hardware_available:
            return None
        if not self._distance_available or self._distance_sensor is None:
            return None
        try:
            return float(self._distance_sensor.distance * 100.0)
        except Exception:
            return None

    def get_warnings(self) -> List[str]:
        """Retourne la liste des avertissements (capteur non détecté ou valeur de repli utilisée)."""
        warnings: List[str] = []
        if not self.is_hardware_available:
            return warnings

        if not self._adc_available or self._adc is None:
            warnings.append(
                "ADC (température / luminosité) non détecté. "
                "Valeurs par défaut utilisées (25 °C, 50 %)."
            )
        else:
            if self._temperature_fallback_used:
                warnings.append(
                    "Température : valeur invalide ou erreur de lecture, "
                    f"valeur par défaut {FALLBACK_TEMPERATURE_C:.0f} °C utilisée."
                )
            if self._luminosity_fallback_used:
                warnings.append(
                    "Luminosité : erreur de lecture, "
                    f"valeur par défaut {FALLBACK_LUMINOSITY_PERCENT:.0f} % utilisée."
                )

        if not self._distance_available or self._distance_sensor is None:
            warnings.append("Détecteur de distance non connecté.")
        else:
            # On ne peut pas savoir si la dernière lecture a échoué sans un flag
            # (read_distance_cm retourne None en cas d'erreur). On n'ajoute pas
            # d'avertissement dynamique pour une lecture échouée ponctuelle.
            pass

        return warnings


@dataclass(frozen=True)
class SensorReadings:
    temperature_c: float
    luminosity_percent: float
