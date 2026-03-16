"""
Tests de l'algorithme d'ouverture automatique (documents/H26-6GP-TP.pdf section 3).

Vérifient que la température et la luminosité influencent l'ouverture
comme dans le document TP : O_T = 5*(T-20), puis O = O_T * F_L si L > 60.
"""

import math

import pytest

from algorithm import (
    DoorOpeningAlgorithm,
    LUMINOSITY_RETARDATION_FACTOR_K,
    LUMINOSITY_RETARDATION_THRESHOLD,
)


def test_tp_example_30c_80_percent_gives_37_5() -> None:
    """Exemple du document TP : T = 30 °C, L = 80 % → O = 37,5 %."""
    o = DoorOpeningAlgorithm.calculate_automatic_opening_percent(30.0, 80.0)
    assert math.isclose(o, 37.5, rel_tol=1e-9, abs_tol=1e-9), (
        f"TP exemple: T=30°C, L=80% doit donner 37.5%, obtenu {o}"
    )


def test_temperature_below_20_gives_zero_opening() -> None:
    """Au-dessous de 20 °C la porte est fermée complètement."""
    for t in (0.0, 10.0, 19.9, 20.0):
        o = DoorOpeningAlgorithm.calculate_automatic_opening_percent(t, 0.0)
        assert math.isclose(o, 0.0, rel_tol=1e-9, abs_tol=1e-9), f"T={t} doit donner 0%, obtenu {o}"


def test_temperature_40_with_no_light_gives_100_percent() -> None:
    """40 °C sans effet luminosité → ouverture 100 %."""
    o = DoorOpeningAlgorithm.calculate_automatic_opening_percent(40.0, 60.0)
    assert math.isclose(o, 100.0, rel_tol=1e-9, abs_tol=1e-9), (
        f"T=40°C, L=60% (pas de retard) doit donner 100%, obtenu {o}"
    )


def test_linear_temperature_effect_20_to_40() -> None:
    """Effet linéaire : 20 °C → 0 %, 40 °C → 100 %, O_T = 5*(T-20)."""
    assert math.isclose(DoorOpeningAlgorithm.calculate_temperature_opening_percent(20.0), 0.0, abs_tol=1e-9)
    assert math.isclose(DoorOpeningAlgorithm.calculate_temperature_opening_percent(40.0), 100.0, abs_tol=1e-9)
    assert math.isclose(
        DoorOpeningAlgorithm.calculate_temperature_opening_percent(30.0),
        50.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def test_light_factor_no_effect_below_60() -> None:
    """L ≤ 60 → aucun effet (F_L = 1)."""
    for l in (0.0, 30.0, 60.0):
        f = DoorOpeningAlgorithm.calculate_light_factor(l)
        assert math.isclose(f, 1.0, rel_tol=1e-9, abs_tol=1e-9), f"L={l} doit donner F_L=1, obtenu {f}"


def test_light_factor_at_100_gives_half() -> None:
    """L = 100 → retard maximal, F_L = 1 - k*1 = 0.5 (k=0.5)."""
    f = DoorOpeningAlgorithm.calculate_light_factor(100.0)
    expected = 1.0 - LUMINOSITY_RETARDATION_FACTOR_K * (100.0 - LUMINOSITY_RETARDATION_THRESHOLD) / 40.0
    assert math.isclose(f, expected, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(f, 0.5, rel_tol=1e-9, abs_tol=1e-9)


def test_opening_clamped_between_0_and_100() -> None:
    """Résultat final 0 ≤ O ≤ 100."""
    o_low = DoorOpeningAlgorithm.calculate_automatic_opening_percent(15.0, 0.0)
    o_high = DoorOpeningAlgorithm.calculate_automatic_opening_percent(50.0, 0.0)
    assert math.isclose(o_low, 0.0, abs_tol=1e-9)
    assert math.isclose(o_high, 100.0, abs_tol=1e-9)
