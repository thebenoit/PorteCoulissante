"""
Algorithmes de calcul d'ouverture de la porte.

Ce module contient uniquement la logique métier pure (aucun accès matériel ou UI).
"""

from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    """Limite une valeur dans l'intervalle [low, high]."""
    return max(low, min(high, value))


class DoorOpeningAlgorithm:
    """Logique métier : calcul de l'ouverture automatique."""

    @staticmethod
    def calculate_temperature_opening_percent(temperature_c: float) -> float:
        """Effet de la température : 20°C→0%, 40°C→100%, linéaire entre les deux."""
        t = clamp(temperature_c, 0.0, 50.0)
        if t < 20.0:
            return 0.0
        if t > 40.0:
            return 100.0
        return 5.0 * (t - 20.0)

    @staticmethod
    def calculate_light_factor(luminosity_percent: float) -> float:
        """
        Effet de la luminosité :
        - L <= 60 : facteur = 1 (aucun effet)
        - L > 60 : facteur = 1 - 0.5 * ((L - 60) / 40)
        """
        l = clamp(luminosity_percent, 0.0, 100.0)
        if l <= 60.0:
            return 1.0
        return 1.0 - 0.5 * ((l - 60.0) / 40.0)

    @classmethod
    def calculate_automatic_opening_percent(cls, temperature_c: float, luminosity_percent: float) -> float:
        """Calcule l'ouverture automatique finale en % (0–100)."""
        opening_temp = cls.calculate_temperature_opening_percent(temperature_c)
        factor_l = cls.calculate_light_factor(luminosity_percent)
        return clamp(opening_temp * factor_l, 0.0, 100.0)

