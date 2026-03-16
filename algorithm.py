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
TEMP_THRESHOLD_LOW_C = 20.0   # en dessous : porte fermée (0 %)
TEMP_THRESHOLD_HIGH_C = 40.0  # au dessus : ouverture 100 %
TEMP_SLOPE_PER_C = 5.0  # pente linéaire ouverture vs température (sujet)
LUMINOSITY_RETARDATION_THRESHOLD = 60.0   # L > 60 : retard
LUMINOSITY_RETARDATION_FACTOR_K = 0.5     # k dans F_L = 1 - k*(L-60)/40
LUMINOSITY_RETARDATION_DENOMINATOR = 40.0  # (L-60)/40 : 60→0, 100→1


class DoorOpeningAlgorithm:
    """
    Calcul de l'ouverture automatique selon le TP :
    - Effet linéaire température : 20°C → 0 %, 40°C → 100 % → O_T = 5*(T-20)
    - Effet luminosité : L ≤ 60 → aucun ; L > 60 → O = O_T * (1 - k*(L-60)/40)
    - Résultat final 0 ≤ O ≤ 100.
    """

    @classmethod
    def calculate_automatic_opening_percent(cls, temperature_c: float, luminosity_percent: float) -> float:
        """
        Ouverture de la porte automatique (%) selon le sujet.
        Ordre du calcul (identique au PDF) : O_T → clamp 0-100 → si L>60 appliquer F_L → clamp final.
        """
        t = clamp(temperature_c, 0.0, 50.0)
        l = clamp(luminosity_percent, 0.0, 100.0)

        # Étape 1 : O_T = 5 * (T - 20)
        o = TEMP_SLOPE_PER_C * (t - TEMP_THRESHOLD_LOW_C)
        if o < 0:
            o = 0.0
        if o > 100:
            o = 100.0

        # Étape 2 : si L > 60, O = O * (1 - k * (L - 60) / 40)
        if l > LUMINOSITY_RETARDATION_THRESHOLD:
            factor_l = 1.0 - LUMINOSITY_RETARDATION_FACTOR_K * (
                (l - LUMINOSITY_RETARDATION_THRESHOLD) / LUMINOSITY_RETARDATION_DENOMINATOR
            )
            o = o * factor_l

        return clamp(o, 0.0, 100.0)

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

