"""
Algorithmes de calcul d'ouverture de la porte.

Conforme au TP H26-6GP : température 20°C→0%, 40°C→100%, luminosité >60% retarde
avec facteur k = 0.5. Formule : O = O_T * F_L avec O_T = 5*(T-20), F_L = 1 si L≤60
sinon F_L = 1 - k*(L-60)/40.
"""

from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    """Limite une valeur dans l'intervalle [low, high]."""
    return max(low, min(high, value))


# Constantes du sujet (documents/H26-6GP-TP.pdf section 3)
# Variables du TP : T température °C (0-50), L luminosité % (0-100), O ouverture % (0-100)
TEMP_THRESHOLD_LOW_C = 20.0   # en dessous : porte fermée
TEMP_THRESHOLD_HIGH_C = 40.0   # au dessus : ouverture max
TEMP_SLOPE_PER_C = 5.0        # pente O_T = 5*(T-20)
LUMINOSITY_RETARDATION_THRESHOLD = 60.0
LUMINOSITY_RETARDATION_FACTOR_K = 0.5      # k du TP
LUMINOSITY_RETARDATION_DENOMINATOR = 40.0


class DoorOpeningAlgorithm:
    """
    Calcul de l'ouverture automatique selon le TP (H26-6GP-TP.pdf section 3).

    Formule du document :
      O = 5 * (T - 20)
      if O < 0: O = 0
      if O > 100: O = 100
      if L > 60: O = O * (1 - k * (L - 60) / 40)
    avec 0 ≤ O ≤ 100. La température et la luminosité influencent donc
    l'ouverture automatique comme dans le document TP.
    """

    @classmethod
    def calculate_automatic_opening_percent(cls, temperature_c: float, luminosity_percent: float) -> float:
        """
        Ouverture de la porte automatique (%) : température + luminosité (TP).
        Code du calcul identique au PDF (variables T, L, O, k).
        """
        T = clamp(temperature_c, 0.0, 50.0)
        L = clamp(luminosity_percent, 0.0, 100.0)
        k = LUMINOSITY_RETARDATION_FACTOR_K

        # Code du calcul (PDF) : O = 5 * (T - 20)
        O = TEMP_SLOPE_PER_C * (T - TEMP_THRESHOLD_LOW_C)
        if O < 0:
            O = 0.0
        if O > 100:
            O = 100.0
        if L > LUMINOSITY_RETARDATION_THRESHOLD:
            O = O * (1.0 - k * (L - LUMINOSITY_RETARDATION_THRESHOLD) / LUMINOSITY_RETARDATION_DENOMINATOR)

        return clamp(O, 0.0, 100.0)

    @staticmethod
    def calculate_temperature_opening_percent(temperature_c: float) -> float:
        """Effet température seul (20°C→0%, 40°C→100%). Utilisé pour tests / cohérence."""
        t = clamp(temperature_c, 0.0, 50.0)
        if t < TEMP_THRESHOLD_LOW_C:
            return 0.0
        if t > TEMP_THRESHOLD_HIGH_C:
            return 100.0
        return TEMP_SLOPE_PER_C * (t - TEMP_THRESHOLD_LOW_C)

    @staticmethod
    def calculate_light_factor(luminosity_percent: float) -> float:
        """Facteur F_L : 1 si L≤60, sinon 1 - k*(L-60)/40. Utilisé pour tests / cohérence."""
        l = clamp(luminosity_percent, 0.0, 100.0)
        if l <= LUMINOSITY_RETARDATION_THRESHOLD:
            return 1.0
        return 1.0 - LUMINOSITY_RETARDATION_FACTOR_K * (
            (l - LUMINOSITY_RETARDATION_THRESHOLD) / LUMINOSITY_RETARDATION_DENOMINATOR
        )

