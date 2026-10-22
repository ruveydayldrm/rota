from app.geo import haversine_km, nearest_neighbor_order, path_length_km
from app.pipeline.schedule import fmt_hhmm, order_stops, parse_hhmm, round5, schedule_times

from .conftest import PLACES

ISTANBUL = (41.0082, 28.9784)
ANKARA = (39.9334, 32.8597)


def test_haversine_known_distance():
    assert 345 < haversine_km(ISTANBUL, ANKARA) < 355
    assert haversine_km(ISTANBUL, ISTANBUL) == 0


def test_path_length_sums_legs():
    pts = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    assert abs(path_length_km(pts) - 2 * haversine_km(pts[0], pts[1])) < 1e-9


def test_nearest_neighbor_visits_close_points_first():
    pts = [(0.0, 0.0), (0.0, 3.0), (0.0, 1.0), (0.0, 2.0)]
    assert nearest_neighbor_order(pts, 0) == [0, 2, 3, 1]
    assert nearest_neighbor_order([], 0) == []


def test_time_helpers():
    assert parse_hhmm("09:30") == 570
    assert parse_hhmm("9") is None and parse_hhmm("24:00") is None
    assert fmt_hhmm(570) == "09:30"
    assert round5(572.4) == 570 and round5(572.5) == 575


def test_order_puts_lunch_near_midday():
    ordered = order_stops(PLACES[:4] + [PLACES[7]], "yuruyus", start=9 * 60, anchor_id="r4")
    assert ordered[0].id == "r4"
    lunch_pos = [p.id for p in ordered].index("n8")
    times = schedule_times(ordered, [10.0] * (len(ordered) - 1), 9 * 60)
    lunch = parse_hhmm(times[lunch_pos])
    assert lunch is not None and 11 * 60 <= lunch <= 14 * 60


def test_schedule_adds_visit_and_travel_time():
    museum, cami = PLACES[3], PLACES[0]  # müze 75 dk
    assert schedule_times([museum, cami], [12.0], 9 * 60) == ["09:00", "10:25"]
