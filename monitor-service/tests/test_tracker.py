"""
ContactTracker unit tests.

The tracker performs no I/O, so everything here is a synthetic Aircraft list
and a clock value. There is nothing to mock — if a test in this file ever needs
a mock, the separation between tracker, state and history has gone wrong.
"""

import threading

import pytest

from controller.tracker import ContactTracker
from models import (
    Aircraft,
    ContactClosed,
    ContactOpened,
    ContactUpdated,
    UNKNOWN,
)


def make_aircraft(hex_code, distance=10.0, **overrides):
    fields = {
        "hex": hex_code,
        "flight": UNKNOWN,
        "altitude": 30000,
        "speed": 450,
        "heading": 90,
        "lat": 45.0,
        "lon": -75.0,
        "distance": distance,
        "bearing": 180.0,
        "origin": UNKNOWN,
        "destination": UNKNOWN,
        "type": UNKNOWN,
        "reg": UNKNOWN,
    }
    fields.update(overrides)
    return Aircraft(**fields)


@pytest.fixture
def tracker():
    return ContactTracker(contact_gap_seconds=300)


def events_of(events, kind):
    return [e for e in events if isinstance(e, kind)]


# --- Contact open ---------------------------------------------------------

def test_first_sweep_opens_a_contact(tracker):
    events = tracker.update([make_aircraft("abc123", distance=12.5)], now=1000.0)

    opened = events_of(events, ContactOpened)
    assert len(opened) == 1
    contact = opened[0].contact
    assert contact.hex == "abc123"
    assert contact.first_seen == 1000.0
    assert contact.last_seen == 1000.0
    assert contact.sample_count == 1
    assert tracker.aircraft_count == 1


def test_second_sweep_updates_rather_than_reopens(tracker):
    tracker.update([make_aircraft("abc123", distance=12.5)], now=1000.0)
    events = tracker.update([make_aircraft("abc123", distance=9.0)], now=1002.0)

    assert events_of(events, ContactOpened) == []
    updated = events_of(events, ContactUpdated)
    assert len(updated) == 1
    assert updated[0].previous.distance == 12.5
    assert updated[0].contact.aircraft.distance == 9.0
    assert updated[0].contact.sample_count == 2
    assert tracker.aircraft_count == 1


def test_contact_updated_carries_previous_telemetry(tracker):
    tracker.update([make_aircraft("abc123", distance=20.0, altitude=31000)], now=1000.0)
    events = tracker.update([make_aircraft("abc123", distance=18.0, altitude=29000)], now=1002.0)

    previous = events_of(events, ContactUpdated)[0].previous
    assert previous.distance == 20.0
    assert previous.altitude == 31000


# --- Identity merge -------------------------------------------------------

def test_identity_merge_prefers_known_over_unknown(tracker):
    tracker.update([make_aircraft("abc123", flight="ACA123", type="B738", reg="C-GABC")], now=1000.0)
    # A later sweep comes back less identified, as readsb routinely does.
    tracker.update([make_aircraft("abc123", flight=UNKNOWN, type=UNKNOWN, reg=UNKNOWN)], now=1002.0)

    contact = tracker.get_contact("abc123")
    assert contact.flight == "ACA123"
    assert contact.aircraft_type == "B738"
    assert contact.registration == "C-GABC"


def test_identity_merge_takes_a_later_known_value(tracker):
    tracker.update([make_aircraft("abc123", flight=UNKNOWN)], now=1000.0)
    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1002.0)

    assert tracker.get_contact("abc123").flight == "ACA123"


def test_identity_merge_ignores_blank_and_whitespace(tracker):
    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1000.0)
    tracker.update([make_aircraft("abc123", flight="   ")], now=1002.0)

    assert tracker.get_contact("abc123").flight == "ACA123"


def test_identity_merge_strips_whitespace(tracker):
    tracker.update([make_aircraft("abc123", flight="  ACA123  ")], now=1000.0)
    assert tracker.get_contact("abc123").flight == "ACA123"


def test_telemetry_is_not_sticky(tracker):
    tracker.update([make_aircraft("abc123", altitude=31000, speed=460)], now=1000.0)
    tracker.update([make_aircraft("abc123", altitude=28000, speed=430)], now=1002.0)

    contact = tracker.get_contact("abc123")
    assert contact.aircraft.altitude == 28000
    assert contact.aircraft.speed == 430


def test_apply_identity_merges_without_overwriting(tracker):
    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1000.0)

    assert tracker.apply_identity("abc123", origin="YOW", destination="LHR")
    assert tracker.get_contact("abc123").origin == "YOW"

    # A later lookup that fails must not erase what we already resolved.
    tracker.apply_identity("abc123", origin=UNKNOWN, destination=UNKNOWN)
    contact = tracker.get_contact("abc123")
    assert contact.origin == "YOW"
    assert contact.destination == "LHR"


def test_apply_identity_reports_a_missing_contact(tracker):
    assert tracker.apply_identity("nope", origin="YOW") is False


def test_to_aircraft_overlays_sticky_identity(tracker):
    tracker.update([make_aircraft("abc123", flight="ACA123", type="B738")], now=1000.0)
    tracker.apply_identity("abc123", origin="YOW", destination="LHR")
    # A bare sweep with no identity at all.
    tracker.update([make_aircraft("abc123", distance=4.0)], now=1002.0)

    aircraft = tracker.all_aircraft[0]
    assert aircraft.distance == 4.0
    assert aircraft.flight == "ACA123"
    assert aircraft.type == "B738"
    assert aircraft.origin == "YOW"
    assert aircraft.destination == "LHR"


# --- Closest approach and envelope ---------------------------------------

def test_closest_approach_tracks_the_minimum(tracker):
    tracker.update([make_aircraft("abc123", distance=20.0, bearing=90.0)], now=1000.0)
    tracker.update([make_aircraft("abc123", distance=3.2, bearing=270.0)], now=1002.0)
    tracker.update([make_aircraft("abc123", distance=15.0, bearing=45.0)], now=1004.0)

    contact = tracker.get_contact("abc123")
    assert contact.closest_nm == 3.2
    assert contact.closest_at == 1002.0
    assert contact.closest_bearing == 270.0


def test_altitude_and_speed_envelope(tracker):
    tracker.update([make_aircraft("abc123", altitude=30000, speed=440)], now=1000.0)
    tracker.update([make_aircraft("abc123", altitude=24000, speed=470)], now=1002.0)
    tracker.update([make_aircraft("abc123", altitude=35000, speed=410)], now=1004.0)

    contact = tracker.get_contact("abc123")
    assert contact.min_altitude == 24000
    assert contact.max_altitude == 35000
    assert contact.max_speed == 470


def test_unreported_altitude_does_not_poison_the_envelope(tracker):
    # readsb sends 0 for "not reported", not "on the ground at a standstill".
    tracker.update([make_aircraft("abc123", altitude=30000, speed=440)], now=1000.0)
    tracker.update([make_aircraft("abc123", altitude=0, speed=0)], now=1002.0)

    contact = tracker.get_contact("abc123")
    assert contact.min_altitude == 30000
    assert contact.max_speed == 440


# --- Gap timeout and departure sweep --------------------------------------

def test_contact_stays_open_inside_the_gap_window(tracker):
    tracker.update([make_aircraft("abc123")], now=1000.0)
    events = tracker.update([], now=1000.0 + 299.0)

    assert events_of(events, ContactClosed) == []
    assert tracker.aircraft_count == 1


def test_contact_closes_after_the_gap_timeout(tracker):
    tracker.update([make_aircraft("abc123", flight="ACA123", distance=6.0)], now=1000.0)
    events = tracker.update([], now=1000.0 + 301.0)

    closed = events_of(events, ContactClosed)
    assert len(closed) == 1
    assert closed[0].contact.hex == "abc123"
    assert closed[0].contact.flight == "ACA123"
    assert closed[0].contact.closest_nm == 6.0
    assert tracker.aircraft_count == 0


def test_departure_sweep_runs_on_an_empty_list(tracker):
    # The whole point: during quiet periods update() is only ever called with
    # an empty list, and contacts still have to close.
    tracker.update([make_aircraft("aaa111"), make_aircraft("bbb222")], now=1000.0)

    assert events_of(tracker.update([], now=1100.0), ContactClosed) == []
    closed = events_of(tracker.update([], now=1400.0), ContactClosed)
    assert {e.contact.hex for e in closed} == {"aaa111", "bbb222"}
    assert tracker.aircraft_count == 0


def test_reappearance_after_timeout_is_a_new_visit(tracker):
    tracker.update([make_aircraft("abc123")], now=1000.0)
    tracker.update([], now=1400.0)
    tracker.update([make_aircraft("abc123")], now=1500.0)

    contact = tracker.get_contact("abc123")
    assert contact.first_seen == 1500.0
    assert contact.sample_count == 1


def test_close_all_closes_everything(tracker):
    tracker.update([make_aircraft("aaa111"), make_aircraft("bbb222")], now=1000.0)
    closed = events_of(tracker.close_all(now=1010.0), ContactClosed)

    assert {e.contact.hex for e in closed} == {"aaa111", "bbb222"}
    assert tracker.aircraft_count == 0
    assert tracker.current_display_target is None


# --- Sticky-closest display target ----------------------------------------

def test_display_target_picks_closest_when_nothing_displayed(tracker):
    tracker.update(
        [make_aircraft("far", distance=30.0), make_aircraft("near", distance=5.0)],
        now=1000.0,
    )
    assert tracker.current_display_target.hex == "near"


def test_display_target_is_sticky_while_in_range(tracker):
    tracker.update([make_aircraft("near", distance=5.0)], now=1000.0)
    # Another aircraft appears further away — must not steal the display.
    tracker.update(
        [make_aircraft("near", distance=8.0), make_aircraft("other", distance=9.0)],
        now=1002.0,
    )
    assert tracker.current_display_target.hex == "near"


def test_display_target_switches_only_when_strictly_closer(tracker):
    tracker.update([make_aircraft("first", distance=10.0)], now=1000.0)
    # Exactly equal distance is not strictly closer — keep the current one.
    tracker.update(
        [make_aircraft("first", distance=10.0), make_aircraft("second", distance=10.0)],
        now=1002.0,
    )
    assert tracker.current_display_target.hex == "first"

    tracker.update(
        [make_aircraft("second", distance=4.0), make_aircraft("first", distance=10.0)],
        now=1004.0,
    )
    assert tracker.current_display_target.hex == "second"


def test_display_target_falls_back_when_current_leaves_range(tracker):
    tracker.update(
        [make_aircraft("near", distance=5.0), make_aircraft("far", distance=30.0)],
        now=1000.0,
    )
    assert tracker.current_display_target.hex == "near"

    # "near" is gone from this sweep even though its contact is still open.
    tracker.update([make_aircraft("far", distance=28.0)], now=1002.0)
    assert tracker.current_display_target.hex == "far"


def test_display_target_clears_on_an_empty_sweep(tracker):
    tracker.update([make_aircraft("near", distance=5.0)], now=1000.0)
    tracker.update([], now=1002.0)

    assert tracker.current_display_target is None
    assert tracker.closest_aircraft is None
    # The contact itself is still open — only the display selection cleared.
    assert tracker.aircraft_count == 1


def test_display_target_survives_being_overtaken_within_hysteresis(tracker):
    """
    The switch rule compares this sweep's closest against the target's distance
    as of the *previous* cycle. That one-cycle hysteresis is what stops the
    E-Ink flipping between two aircraft that are converging on each other.
    """
    tracker.update(
        [make_aircraft("a", distance=5.0), make_aircraft("b", distance=8.0)],
        now=1000.0,
    )
    assert tracker.current_display_target.hex == "a"

    tracker.update(
        [make_aircraft("a", distance=6.0), make_aircraft("b", distance=7.5)],
        now=1002.0,
    )
    assert tracker.current_display_target.hex == "a"

    # "b" is nearer than "a" in this sweep (6.5 vs 7.0), but not nearer than
    # "a" was last cycle (6.0), so the display holds.
    tracker.update(
        [make_aircraft("a", distance=7.0), make_aircraft("b", distance=6.5)],
        now=1004.0,
    )
    assert tracker.current_display_target.hex == "a"


def test_closest_aircraft_is_independent_of_the_display_target(tracker):
    tracker.update([make_aircraft("a", distance=5.0)], now=1000.0)
    # "b" is the nearest thing in this sweep but is not closer than "a" was, so
    # the display stays on "a" while closest_aircraft reports "b".
    tracker.update(
        [make_aircraft("a", distance=7.0), make_aircraft("b", distance=6.0)],
        now=1002.0,
    )

    assert tracker.closest_aircraft.hex == "b"
    assert tracker.current_display_target.hex == "a"


def test_all_aircraft_is_sorted_nearest_first(tracker):
    tracker.update(
        [
            make_aircraft("c", distance=30.0),
            make_aircraft("a", distance=2.0),
            make_aircraft("b", distance=11.0),
        ],
        now=1000.0,
    )
    assert [ac.hex for ac in tracker.all_aircraft] == ["a", "b", "c"]


def test_reads_return_copies(tracker):
    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1000.0)

    aircraft = tracker.all_aircraft[0]
    aircraft.flight = "MUTATED"
    assert tracker.all_aircraft[0].flight == "ACA123"

    contact = tracker.get_contact("abc123")
    contact.flight = "MUTATED"
    assert tracker.get_contact("abc123").flight == "ACA123"


# --- Subscription ---------------------------------------------------------

def test_subscribers_receive_events_in_order(tracker):
    seen = []
    tracker.subscribe(seen.append)

    tracker.update([make_aircraft("abc123")], now=1000.0)
    tracker.update([make_aircraft("abc123")], now=1002.0)
    tracker.update([], now=1400.0)

    assert [type(e).__name__ for e in seen] == [
        "ContactOpened",
        "ContactUpdated",
        "ContactClosed",
    ]


def test_a_raising_subscriber_cannot_kill_the_loop(tracker):
    def explode(_event):
        raise RuntimeError("subscriber is having a bad day")

    survivors = []
    tracker.subscribe(explode)
    tracker.subscribe(survivors.append)

    tracker.update([make_aircraft("abc123")], now=1000.0)

    assert len(survivors) == 1
    assert tracker.aircraft_count == 1


def test_handlers_are_dispatched_outside_the_lock(tracker):
    """
    HistoryStore does SQLite I/O in its handler. If dispatch ran while holding
    the tracker lock, every API read would block for the duration of a disk
    write. Simulate that: a slow handler must not stall a reader on another
    thread.
    """
    handler_running = threading.Event()
    reader_finished = threading.Event()

    def slow_handler(_event):
        handler_running.set()
        # Stands in for the SQLite write. Long enough that a reader blocked on
        # the tracker lock would visibly fail the assertion below.
        reader_finished.wait(2.0)

    def reader():
        handler_running.wait(2.0)
        # This takes the tracker lock. It must not be held by the dispatcher.
        assert tracker.aircraft_count == 1
        reader_finished.set()

    tracker.subscribe(slow_handler)
    reader_thread = threading.Thread(target=reader)
    reader_thread.start()

    tracker.update([make_aircraft("abc123")], now=1000.0)
    reader_thread.join(timeout=3.0)

    assert not reader_thread.is_alive()
    assert reader_finished.is_set(), "reader blocked — dispatch is holding the lock"
