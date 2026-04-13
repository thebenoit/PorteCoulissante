import math

from sensors import (
    CLOSED_DISTANCE_CM,
    OPEN_DISTANCE_CM,
    compute_door_position_from_distance,
)


def test_compute_door_position_from_distance_closed():
    pos = compute_door_position_from_distance(CLOSED_DISTANCE_CM)
    assert math.isclose(pos, 0.0, rel_tol=1e-6, abs_tol=1e-6)


def test_compute_door_position_from_distance_open():
    pos = compute_door_position_from_distance(OPEN_DISTANCE_CM)
    assert math.isclose(pos, 1.0, rel_tol=1e-6, abs_tol=1e-6)


def test_compute_door_position_from_distance_midpoint():
    mid = (CLOSED_DISTANCE_CM + OPEN_DISTANCE_CM) / 2.0
    pos = compute_door_position_from_distance(mid)
    assert math.isclose(pos, 0.5, rel_tol=1e-6, abs_tol=1e-6)


def test_compute_door_position_from_distance_below_closed_clamped():
    pos = compute_door_position_from_distance(CLOSED_DISTANCE_CM - 10.0)
    assert math.isclose(pos, 0.0, rel_tol=1e-6, abs_tol=1e-6)


def test_compute_door_position_from_distance_above_open_clamped():
    pos = compute_door_position_from_distance(OPEN_DISTANCE_CM + 10.0)
    assert math.isclose(pos, 1.0, rel_tol=1e-6, abs_tol=1e-6)

