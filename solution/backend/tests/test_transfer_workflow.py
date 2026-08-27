from datetime import datetime, timezone

import pytest

from transfer_workflow import travel_metrics_str

NOW = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

# New York -> London, roughly 5570km apart.
NY = (40.7128, -74.0060)
LONDON = (51.5074, -0.1278)


def test_travel_metrics_aware_timestamp_does_not_raise():
    result = travel_metrics_str(*NY, "2026-01-01T12:00:00+00:00", *LONDON, NOW)
    assert "km" in result and "km/h" in result


def test_travel_metrics_naive_timestamp_does_not_raise():
    # Regression test: this exact input (no UTC offset) used to raise
    # "can't subtract offset-naive and offset-aware datetimes" when the model reformatted the
    # timestamp without its timezone suffix - the Agent then reported that as a repeated tool
    # error and declined the whole transfer as a fallback, not an actual fraud determination.
    result = travel_metrics_str(*NY, "2026-01-01T12:00:00", *LONDON, NOW)
    assert "km" in result and "km/h" in result


def test_travel_metrics_naive_and_aware_agree_for_the_same_instant():
    aware = travel_metrics_str(*NY, "2026-01-01T12:00:00+00:00", *LONDON, NOW)
    naive = travel_metrics_str(*NY, "2026-01-01T12:00:00", *LONDON, NOW)
    assert aware == naive


def test_travel_metrics_distance_is_realistic_for_ny_to_london():
    result = travel_metrics_str(*NY, "2026-01-01T00:00:00+00:00", *LONDON, NOW)
    distance_km = int(result.split(" km")[0])
    assert 5400 <= distance_km <= 5700


def test_travel_metrics_zero_elapsed_time_does_not_divide_by_zero():
    # last transaction "now" and this transaction also "now" - elapsed_hours is clamped to a tiny
    # positive floor (1e-6h) rather than zero, so the speed division can't blow up.
    result = travel_metrics_str(*NY, NOW.isoformat(), *LONDON, NOW)
    assert "km/h" in result


def test_travel_metrics_same_point_is_zero_distance():
    result = travel_metrics_str(*NY, "2026-01-01T00:00:00+00:00", *NY, NOW)
    distance_km = int(result.split(" km")[0])
    assert distance_km == 0
