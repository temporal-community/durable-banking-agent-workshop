from __future__ import annotations

import math

from geo import haversine_km

NEW_YORK = (40.7128, -74.0060)
LONDON = (51.5074, -0.1278)


def test_haversine_identical_points_is_zero():
    assert haversine_km(*NEW_YORK, *NEW_YORK) == 0.0


def test_haversine_known_real_world_distance():
    # New York to London is ~5570 km great-circle.
    distance = haversine_km(*NEW_YORK, *LONDON)
    assert 5500 <= distance <= 5650


def test_haversine_is_symmetric():
    a_to_b = haversine_km(*NEW_YORK, *LONDON)
    b_to_a = haversine_km(*LONDON, *NEW_YORK)
    assert a_to_b == b_to_a


def test_haversine_antipodal_points_is_half_circumference():
    # (0, 0) and its antipode (0, 180) are as far apart as two points on Earth can be:
    # half the circumference, pi * R.
    distance = haversine_km(0.0, 0.0, 0.0, 180.0)
    expected = math.pi * 6371.0
    assert abs(distance - expected) < 1.0


def test_haversine_short_distance_is_small_and_positive():
    # ~0.01 degree of latitude at the equator is about 1.1 km.
    distance = haversine_km(0.0, 0.0, 0.01, 0.0)
    assert 0.0 < distance < 2.0
