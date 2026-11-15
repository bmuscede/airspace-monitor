"""
Split-flap layout tests.

No hardware and no serial port: SplitFlapDriver is replaced with a stub that records what it
was asked to show, which is enough to pin down the part that makes decisions — which layout
fits the flaps that are actually configured, and when the display is written to at all.
"""

import json

from display.splitflap_display import SplitFlapDisplay
from splitflap.config import SplitFlapConfig
from models import UNKNOWN, Aircraft, StateInformation, WeatherDay, WeatherForecast
from utils.config import ConfigManager

# The flaps the service ships as its default charset, plus a logo charset for
# the first position of the top row.
DEFAULT_FLAPS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!?."
# A logo spool: the airlines we have flaps cut for, padded out to the same
# forty flaps every other module carries.
LOGO_FLAPS = [" ", "ACA", "AAL", "DAL", "SWA", "FDX", "WJA", "TSC"] + [" "] * 32


class FakeDriver:
    """Stands in for SplitFlapDriver: remembers the last show() call."""

    def __init__(self, config: SplitFlapConfig):
        self.config = config
        self.shown = []

    @property
    def num_positions(self):
        return len(self.config.positions)

    def show(self, tokens, align="left", force_rotation=False):
        self.shown.append(list(tokens))
        return []


def make_display(tmp_path, rows=None, positions=None, logo_first=False, calibrated=True):
    """A SplitFlapDisplay wired to a FakeDriver. Enough flaps for `rows` by default."""
    if positions is None:
        positions = sum(rows) if rows else 14
    channels = [{"channel": i, "charset": "default"} for i in range(positions)]
    if logo_first:
        channels[0] = {"channel": 0, "charset": "logos"}

    (tmp_path / "config.json").write_text(json.dumps({
        "splitflap": {
            # Left disabled: __init__ then opens no port and starts no threads,
            # and the driver is substituted by hand below.
            "enabled": False,
            "rows": rows or [],
            "channels": channels,
            "charsets": {
                "default": {"flaps": DEFAULT_FLAPS},
                "logos": {"flaps": LOGO_FLAPS, "aliases": {"ROU": "ACA"}},
            },
            "calibration": {"calibrated": calibrated},
        },
    }), encoding="utf-8")

    manager = ConfigManager(str(tmp_path))
    display = SplitFlapDisplay(manager)
    assert display._driver is None, "a disabled display must not open a port"

    config = display._buildConfig()
    display._driver = FakeDriver(config)
    return display


def text(display):
    """What the last show() call puts on the flaps, row by row."""
    tokens = display._driver.shown[-1]
    return ["".join(t if len(t) == 1 else "{" + t + "}" for t in tokens[start:start + length])
            for start, length in display._rows]


def make_aircraft(**overrides):
    fields = {
        "hex": "c01234",
        "flight": "ACA857",
        "origin": "YYZ",
        "destination": "YVR",
        "type": "B789",
        "reg": "CFVLQ",
        "altitude": 36000,
        "speed": 480,
        "heading": 270,
    }
    fields.update(overrides)
    return Aircraft(**fields)


def test_a_disabled_display_writes_nothing(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"splitflap": {"enabled": False}}), encoding="utf-8")
    display = SplitFlapDisplay(ConfigManager(str(tmp_path)))

    display.write_flight_data(make_aircraft())

    assert display._driver is None


def test_a_display_with_no_channels_stays_off(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"splitflap": {"enabled": True, "channels": []}}), encoding="utf-8")
    manager = ConfigManager(str(tmp_path))
    display = SplitFlapDisplay(manager)

    assert display._buildConfig() is None


def test_three_rows_show_the_flight_the_route_and_the_type(tmp_path):
    display = make_display(tmp_path, rows=[14, 14, 14])

    display.write_flight_data(make_aircraft())

    # The stock charset has no hyphen, so the space separator wins.
    assert text(display) == ["    ACA857    ", "   YYZ YVR    ", "     B789     "]


def test_an_airline_with_a_logo_flap_uses_it(tmp_path):
    display = make_display(tmp_path, rows=[14, 14, 14], logo_first=True)

    display.write_flight_data(make_aircraft())

    # The logo charset only sits at position 0, so that is where the layout has
    # to put it: the row is left-aligned and the flight number follows the logo.
    # Four flaps of the fourteen are used; a logo reads as {ACA} here.
    assert text(display)[0] == "{ACA}857" + " " * 10


def test_a_single_row_display_gets_one_line(tmp_path):
    display = make_display(tmp_path, positions=14)

    display.write_flight_data(make_aircraft())

    # "ACA857 YYZ YVR" is exactly fourteen flaps.
    assert text(display) == ["ACA857 YYZ YVR"]


def test_a_short_row_drops_the_route_rather_than_truncating_it(tmp_path):
    display = make_display(tmp_path, positions=8)

    display.write_flight_data(make_aircraft())

    assert text(display) == [" ACA857 "]


def test_an_unidentified_aircraft_falls_back_to_its_registration_then_its_hex(tmp_path):
    display = make_display(tmp_path, rows=[10, 10])

    display.write_flight_data(make_aircraft(flight=UNKNOWN, origin=UNKNOWN, destination=UNKNOWN))
    assert text(display)[0] == "  CFVLQ   "

    display.write_flight_data(make_aircraft(flight=UNKNOWN, reg=UNKNOWN, origin=UNKNOWN, destination=UNKNOWN))
    assert text(display)[0] == "  C01234  "


def test_an_empty_sky_says_so(tmp_path):
    display = make_display(tmp_path, rows=[14, 14])
    state = StateInformation(readsb_connected=True, range=50, uptime="1:00:00", daily_seen=3, total_seen=9)

    display.write_no_flight(state, None)

    assert text(display) == ["  NO FLIGHTS  ", "              "]


def test_the_forecast_goes_under_the_headline_without_its_degree_sign(tmp_path):
    display = make_display(tmp_path, rows=[14, 14])
    state = StateInformation(readsb_connected=True, range=50, uptime="1:00:00", daily_seen=3, total_seen=9)
    forecast = WeatherForecast(
        city_name="Toronto",
        location_name="Toronto, CA",
        forecast=[WeatherDay(day="MON", high="12°C", low="4°C", description="clear", icon="clear-day")],
    )

    display.write_no_flight(state, forecast)

    assert text(display) == ["  NO FLIGHTS  ", "    12C 4C    "]


def test_a_dead_receiver_is_reported_instead_of_an_empty_sky(tmp_path):
    display = make_display(tmp_path, rows=[14])
    state = StateInformation(readsb_connected=False, range=50, uptime="1:00:00", daily_seen=0, total_seen=0)

    display.write_no_flight(state, None)

    assert text(display) == ["   NO RADAR   "]


def test_the_same_frame_is_only_written_once(tmp_path):
    display = make_display(tmp_path, rows=[14, 14, 14])
    aircraft = make_aircraft()

    display.write_flight_data(aircraft)
    display.write_flight_data(aircraft)
    # Altitude and speed are not on the flaps, so a new sweep of the same
    # aeroplane must not turn a single module.
    display.write_flight_data(make_aircraft(altitude=35000, speed=500))

    assert len(display._driver.shown) == 1


def test_nothing_is_written_while_the_display_is_calibrating(tmp_path):
    display = make_display(tmp_path, rows=[14])
    display._calibrating.set()

    display.write_flight_data(make_aircraft())

    assert display._driver.shown == []


def test_rows_that_do_not_fit_the_channels_fall_back_to_one_row(tmp_path):
    display = make_display(tmp_path, rows=[14, 14], positions=14)

    assert display._rows == [(0, 14)]


def test_calibration_is_skipped_once_the_config_remembers_it(tmp_path):
    display = make_display(tmp_path, rows=[14], calibrated=True)

    assert display.IsCalibrated() is True
    # Nothing was asked of the display: no rehome, no save.
    assert display.Calibrate() is True
    assert display._driver.shown == []


def test_an_uncalibrated_display_is_calibrated_and_remembered(tmp_path):
    display = make_display(tmp_path, rows=[14], calibrated=False)
    calls = []

    class Calibrating(FakeDriver):
        def rehome(self, positions=None):
            calls.append("rehome")

        def wait_until_idle(self, positions=None, timeout=60.0):
            calls.append("wait")
            return True

        def status(self):
            return _HealthyStatus()

        def add_log_listener(self, callback):
            self._on_log = callback
            return lambda: None

        def save_calibration(self):
            calls.append("save")
            self._on_log("SUCCESS - saved calibration!")

    display._driver = Calibrating(display._driver.config)

    assert display.IsCalibrated() is False
    assert display.Calibrate() is True
    assert calls == ["rehome", "wait", "save"]

    # Remembered for the next start, on disk as well as in memory.
    assert display.IsCalibrated() is True
    reloaded = ConfigManager(str(tmp_path))
    assert reloaded.Get("splitflap.calibration.calibrated") is True
    assert reloaded.Get("splitflap.calibration.calibrated_at") > 0


def test_a_display_with_faults_is_not_recorded_as_calibrated(tmp_path):
    display = make_display(tmp_path, rows=[14], calibrated=False)

    class Faulty(FakeDriver):
        def rehome(self, positions=None):
            pass

        def wait_until_idle(self, positions=None, timeout=60.0):
            return True

        def status(self):
            return _FaultyStatus()

    display._driver = Faulty(display._driver.config)

    assert display.Calibrate() is False
    assert display.IsCalibrated() is False


class _HealthyStatus:
    faults = []


class _FaultyStatus:
    faults = ["position 0 (channel 0): SENSOR_ERROR"]
