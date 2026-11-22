"""
Telemetry arriving as something other than a whole number.

These exist because of a live failure: with real aircraft overhead, every
single radar sweep raised

    2 validation errors for Aircraft
    speed    Input should be a valid integer, got a number with a fractional
             part [input_value=208.9]
    heading  Input should be a valid integer, got a number with a fractional
             part [input_value=164.17]

readsb reports "gs" and "track" as floats; the model declares them int;
Pydantic refuses to narrow a fractional float. The hardware loop caught the
error and skipped the cycle, so the display froze for exactly as long as an
aircraft was in range -- the appliance was broken whenever it had something to
show, and fine when the sky was empty.

Values in the first few tests are taken verbatim from that log.
"""

import json
import logging
import math

import pytest

from controller.controller import Controller
from controller.state import SystemState
from models import Aircraft, StateInformation, UNKNOWN
from utils.config import ConfigManager


def make_aircraft(**overrides):
    fields = {
        "hex": "c06a1b",
        "flight": "ACA123",
        "altitude": 30000,
        "speed": 450,
        "heading": 90,
        "lat": 45.0,
        "lon": -75.0,
        "distance": 10.0,
        "bearing": 180.0,
    }
    fields.update(overrides)
    return Aircraft(**fields)


# --- the reported failure -------------------------------------------------

@pytest.mark.parametrize("speed,heading,want_speed,want_heading", [
    (208.9, 164.17, 209, 164),
    (204.3, 176.91, 204, 177),
    (198.1, 196.42, 198, 196),
])
def test_fractional_telemetry_from_the_log(speed, heading, want_speed, want_heading):
    """The exact values that were aborting sweeps."""
    ac = make_aircraft(speed=speed, heading=heading)
    assert ac.speed == want_speed
    assert ac.heading == want_heading


def test_result_is_really_an_int_not_a_float():
    """
    The E-Ink panel renders these with f"{heading}" into a fixed-width column,
    so a float that merely compares equal would still draw "164.0".
    """
    ac = make_aircraft(speed=208.9, heading=164.17, altitude=35000.0)
    assert type(ac.speed) is int
    assert type(ac.heading) is int
    assert type(ac.altitude) is int


def test_whole_floats_are_accepted_too():
    ac = make_aircraft(speed=450.0, heading=90.0, altitude=30000.0)
    assert (ac.speed, ac.heading, ac.altitude) == (450, 90, 30000)


# --- the other shapes the feeds emit --------------------------------------

def test_alt_baro_ground_is_not_an_altitude():
    """readsb sends the literal string "ground" for an aircraft on the deck."""
    assert make_aircraft(altitude="ground").altitude == 0


def test_missing_fields_become_zero():
    ac = make_aircraft(altitude=None, speed=None, heading=None)
    assert (ac.altitude, ac.speed, ac.heading) == (0, 0, 0)


def test_numeric_strings_are_read():
    ac = make_aircraft(altitude="1200", speed="450", heading="90")
    assert (ac.altitude, ac.speed, ac.heading) == (1200, 450, 90)


def test_unreadable_values_do_not_abort_the_sweep():
    """
    Anything we cannot make a number of becomes 0. A bad field must never be
    able to take down the cycle -- that is the whole point of this change.
    """
    ac = make_aircraft(altitude="n/a", speed="", heading="unknown")
    assert (ac.altitude, ac.speed, ac.heading) == (0, 0, 0)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_infinity_become_zero(value):
    """round() raises on these, which is the failure we are preventing."""
    assert make_aircraft(speed=value).speed == 0


def test_booleans_are_not_treated_as_one_and_zero():
    """bool is an int subclass; True in a speed field is nonsense, not 1 knot."""
    assert make_aircraft(speed=True).speed == 0


def test_negative_altitude_survives():
    """
    alt_baro below zero is real -- Schiphol sits at roughly -11 ft and a
    pressure-altitude reading can go lower still. Coercion must round, not
    clamp.
    """
    assert make_aircraft(altitude=-75.4).altitude == -75


def test_existing_integers_pass_through_untouched():
    ac = make_aircraft(altitude=30000, speed=450, heading=90)
    assert (ac.altitude, ac.speed, ac.heading) == (30000, 450, 90)


# --- heading is a compass direction, not just a number --------------------

@pytest.mark.parametrize("raw,want", [
    (359.7, 0),      # would round to 360, a wider string for the same heading
    (360, 0),
    (360.0, 0),
    (359.4, 359),
    (-10.4, 350),    # some feeds signed the track
    (0.2, 0),
])
def test_heading_wraps_to_a_single_turn(raw, want):
    assert make_aircraft(heading=raw).heading == want


def test_heading_wrap_does_not_touch_speed_or_altitude():
    """Only heading is modular; 360 knots is 360 knots."""
    ac = make_aircraft(speed=360.0, altitude=360.0)
    assert ac.speed == 360
    assert ac.altitude == 360


# --- the same hazard on the idle screen -----------------------------------

def test_state_information_range_accepts_a_fractional_config_value():
    """
    radar.max_range_nm comes straight from config.json, and /api/config checks
    that a key exists but not its type -- so a dashboard or a curl can put
    25.5 in there. Before this, that broke the no-flight screen on every idle
    cycle, which is the identical failure with a different trigger.
    """
    state = StateInformation(
        readsb_connected=True,
        range=25.5,
        uptime="1:00:00",
        daily_seen=3,
        total_seen=9,
    )
    assert state.range == 26
    assert type(state.range) is int


# --- end to end through the real parser -----------------------------------

@pytest.fixture
def parser(tmp_path, monkeypatch):
    """
    The real Controller._read_aircraft, without building a Controller.

    Constructing one starts displays, history and the FlightAware client. The
    parser only reaches for state, configManager and logger, so those are what
    it gets -- a real SystemState and a real ConfigManager, not stubs, so the
    config lookups behave as they do in service.
    """
    controller = Controller.__new__(Controller)
    controller.state = SystemState()
    controller.logger = logging.getLogger("test.parser")
    controller.configManager = ConfigManager(str(tmp_path))
    controller.configManager.Set("radar.home_lat", 45.0)
    controller.configManager.Set("radar.home_lon", -75.0)
    controller.configManager.Set("radar.max_range_nm", 250)

    feed = tmp_path / "aircraft.json"
    monkeypatch.setattr("controller.controller.AIRCRAFT_JSON_PATH", str(feed))
    return controller, feed


def write_feed(path, aircraft):
    path.write_text(json.dumps({"now": 1763750000.0, "aircraft": aircraft}))


def test_real_readsb_payload_parses(parser):
    """
    A sweep shaped like the one that was failing: floats for gs and track, an
    aircraft on the ground, and one that has not reported a speed yet.
    """
    controller, feed = parser
    write_feed(feed, [
        {"hex": "C06A1B", "flight": "ACA123 ", "alt_baro": 31000,
         "gs": 208.9, "track": 164.17, "lat": 45.1, "lon": -75.1},
        {"hex": "a1b2c3", "flight": "UAL88", "alt_baro": "ground",
         "gs": 12.4, "track": 359.7, "lat": 45.05, "lon": -75.02},
        {"hex": "d4e5f6", "alt_baro": 4250.0,
         "lat": 45.2, "lon": -75.2},
    ])

    sweep = controller._read_aircraft()

    assert controller.state.readsb_connected is True
    assert len(sweep) == 3

    by_hex = {ac.hex: ac for ac in sweep}

    first = by_hex["c06a1b"]
    assert (first.speed, first.heading, first.altitude) == (209, 164, 31000)
    assert first.flight == "ACA123"

    grounded = by_hex["a1b2c3"]
    assert grounded.altitude == 0
    assert grounded.heading == 0
    assert grounded.speed == 12

    quiet = by_hex["d4e5f6"]
    assert (quiet.speed, quiet.heading) == (0, 0)
    assert quiet.altitude == 4250
    assert quiet.flight == UNKNOWN


def test_a_fractional_sweep_no_longer_raises(parser):
    """
    The regression itself. Every aircraft in this feed carries the kind of
    value that used to abort the cycle; the sweep must come back whole.
    """
    controller, feed = parser
    write_feed(feed, [
        {"hex": f"00000{i}", "gs": 198.1 + i, "track": 196.42,
         "alt_baro": 10000 + i, "lat": 45.0 + i / 100, "lon": -75.0}
        for i in range(6)
    ])

    sweep = controller._read_aircraft()

    assert len(sweep) == 6
    assert all(type(ac.speed) is int for ac in sweep)
    assert all(type(ac.heading) is int for ac in sweep)
    assert [ac.heading for ac in sweep] == [196] * 6


def test_aircraft_outside_range_still_filtered(parser):
    """The coercion must not have disturbed the range filter."""
    controller, feed = parser
    controller.configManager.Set("radar.max_range_nm", 20)
    write_feed(feed, [
        {"hex": "near01", "gs": 208.9, "track": 164.17, "lat": 45.05, "lon": -75.05},
        {"hex": "far001", "gs": 450.5, "track": 90.5, "lat": 50.0, "lon": -80.0},
    ])

    sweep = controller._read_aircraft()

    assert [ac.hex for ac in sweep] == ["near01"]


def test_positionless_aircraft_still_skipped(parser):
    controller, feed = parser
    write_feed(feed, [
        {"hex": "nopos1", "gs": 208.9, "track": 164.17},
        {"hex": "haspos", "gs": 208.9, "track": 164.17, "lat": 45.01, "lon": -75.01},
    ])

    assert [ac.hex for ac in controller._read_aircraft()] == ["haspos"]


def test_missing_feed_reports_disconnected(parser):
    """The FileNotFoundError path, unchanged but worth holding onto."""
    controller, feed = parser
    assert controller._read_aircraft() == []
    assert controller.state.readsb_connected is False
