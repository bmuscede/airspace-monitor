"""
E-Ink orientation tests.

The case in this repo holds the panel upside down, so the driver turns the
finished image 180 degrees on its way to the hardware. The drawing code above
it stays in reading order, which means this one step is the only thing standing
between a correct layout and an unreadable screen — worth pinning down.

These run without a panel: `epaper` is absent off the Pi, so the constructor
falls back to its 800x480 software size and `_display` is None. A fake panel is
injected where the write path is under test.

The second half covers the panel's wake/sleep lifecycle, which produced a
subtler failure: the driver wrote without waking the panel, so the first
update after start-up worked, every one after it raised "[Errno 9] Bad file
descriptor" inside the hardware loop, and the screen sat on whatever it last
managed to draw.
"""

import errno
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from display.eink_display import EInkDisplay
from utils.config import ConfigManager


class FakePanel:
    """
    Stands in for the Waveshare EPD, lifecycle included.

    The lifecycle is the point, not decoration. The real sleep() ends in
    epdconfig.module_exit(), which calls SPI.close() and drops the panel's
    power pin, so a write afterwards goes to a closed descriptor and spidev
    raises OSError(EBADF) -- "[Errno 9] Bad file descriptor". A fake that
    quietly accepts a write while asleep cannot catch that, which is how the
    bug reached hardware in the first place.
    """

    def __init__(self, init_result=0, fail_on_display=False):
        self.width = 800
        self.height = 480
        self.displayed = None
        self.buffered = None
        self.slept = False
        self.awake = False
        self.calls = []
        self.init_count = 0
        self.sleep_count = 0
        self.display_count = 0
        self._init_result = init_result
        self._fail_on_display = fail_on_display

    def init(self):
        self.calls.append("init")
        self.init_count += 1
        if self._init_result != 0:
            return self._init_result
        self.awake = True
        return 0

    def Clear(self, color=0x11):
        self.calls.append("Clear")
        self._require_awake()

    def getbuffer(self, image):
        # The real driver returns a packed byte buffer. The image itself is
        # what these tests care about, so it is passed straight through.
        self.buffered = image
        return image

    def display(self, buffer):
        self.calls.append("display")
        self.display_count += 1
        self._require_awake()
        if self._fail_on_display:
            raise OSError(errno.EIO, "Input/output error")
        self.displayed = buffer

    def sleep(self):
        self.calls.append("sleep")
        self.sleep_count += 1
        self.slept = True
        self.awake = False

    def _require_awake(self):
        if not self.awake:
            raise OSError(errno.EBADF, "Bad file descriptor")


def fake_epaper_for(panel):
    """A stand-in for the `epaper` package, handing back one fixed panel."""
    return SimpleNamespace(epaper=lambda model: SimpleNamespace(EPD=lambda: panel))


@pytest.fixture
def panel_display(tmp_path, monkeypatch):
    """
    A driver built through its real constructor against a fake panel.

    `_throttle_seconds` is zeroed because these tests write several frames in
    a row: on hardware those are 90 seconds apart, and the throttle would
    otherwise refuse everything after the first and hide what is under test.
    """
    panel = FakePanel()
    monkeypatch.setattr("display.eink_display.epaper", fake_epaper_for(panel))
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    display._throttle_seconds = 0
    return display, panel


def write_config(directory, data):
    (directory / "config.json").write_text(json.dumps(data), encoding="utf-8")


def corner_marked_canvas(width=800, height=480):
    """A white canvas with a single red pixel in the top-left corner."""
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    canvas.putpixel((0, 0), (255, 0, 0))
    return canvas


def test_rotation_is_on_by_default_for_the_case(tmp_path):
    display = EInkDisplay(ConfigManager(str(tmp_path)))

    assert display._rotate_180 is True


def test_rotation_can_be_turned_off_in_the_config(tmp_path):
    write_config(tmp_path, {"eink": {"rotate_180": False}})

    display = EInkDisplay(ConfigManager(str(tmp_path)))

    assert display._rotate_180 is False


def test_a_config_predating_the_option_still_rotates(tmp_path):
    # A config.json written before "eink" existed. Loading merges the
    # defaults in, so the case's orientation is not silently lost.
    write_config(tmp_path, {"radar": {"home_lat": 43.65}})

    display = EInkDisplay(ConfigManager(str(tmp_path)))

    assert display._rotate_180 is True


def test_no_config_manager_still_rotates():
    # A bare driver, as a script or a calibration tool would build it.
    assert EInkDisplay()._rotate_180 is True


def test_orienting_moves_the_corner_to_the_far_side(tmp_path):
    display = EInkDisplay(ConfigManager(str(tmp_path)))

    turned = display._orient_for_panel(corner_marked_canvas())

    # The marked pixel started top-left and belongs bottom-right.
    assert turned.getpixel((799, 479)) == (255, 0, 0)
    assert turned.getpixel((0, 0)) == (255, 255, 255)
    assert turned.size == (800, 480)


def test_orienting_is_a_no_op_when_rotation_is_off(tmp_path):
    write_config(tmp_path, {"eink": {"rotate_180": False}})
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    canvas = corner_marked_canvas()

    assert display._orient_for_panel(canvas) is canvas


def test_the_panel_is_handed_a_turned_image(tmp_path):
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    panel = FakePanel()
    display._display = panel

    display._writeToScreen(corner_marked_canvas())

    assert panel.displayed is not None
    assert panel.displayed.getpixel((799, 479)) == (255, 0, 0)
    assert panel.displayed.getpixel((0, 0)) == (255, 255, 255)
    # The panel is put back to sleep after every write.
    assert panel.slept is True


def test_the_panel_is_handed_an_upright_image_when_rotation_is_off(tmp_path):
    write_config(tmp_path, {"eink": {"rotate_180": False}})
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    panel = FakePanel()
    display._display = panel

    display._writeToScreen(corner_marked_canvas())

    assert panel.displayed.getpixel((0, 0)) == (255, 0, 0)
    assert panel.displayed.getpixel((799, 479)) == (255, 255, 255)


def test_turning_twice_returns_the_original_orientation(tmp_path):
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    canvas = corner_marked_canvas()

    there_and_back = display._orient_for_panel(display._orient_for_panel(canvas))

    assert there_and_back.tobytes() == canvas.tobytes()


def test_a_real_idle_frame_survives_the_turn(tmp_path):
    """
    The whole idle screen through the real drawing code, not a synthetic
    canvas, so a layout that assumes the panel's own width still lands.
    """
    from models import StateInformation, WeatherForecast

    display = EInkDisplay(ConfigManager(str(tmp_path)))
    panel = FakePanel()
    display._display = panel

    display.write_no_flight(
        StateInformation(
            readsb_connected=True,
            range=50,
            uptime="1:00:00",
            daily_seen=3,
            total_seen=9,
        ),
        WeatherForecast(city_name="Ottawa", location_name="Ottawa, CA", forecast=[]),
    )

    assert panel.displayed is not None
    assert panel.displayed.size == (800, 480)


# --- the panel's wake/sleep lifecycle -------------------------------------

def test_the_constructor_leaves_the_panel_asleep(panel_display):
    """
    init, clear, sleep -- in that order, and asleep at the end.

    If the constructor left SPI open, the first write's init() would open it a
    second time and leak the first descriptor.
    """
    _, panel = panel_display

    assert panel.calls == ["init", "Clear", "sleep"]
    assert panel.awake is False


def test_the_panel_is_woken_before_it_is_written_to(panel_display):
    display, panel = panel_display

    assert display._writeToScreen(corner_marked_canvas()) is True

    # init has to come immediately before the write, and sleep after it.
    assert panel.calls[-3:] == ["init", "display", "sleep"]


def test_a_second_write_does_not_hit_a_closed_descriptor(panel_display):
    """
    The regression. Before the fix the first write succeeded and every one
    after it raised OSError(EBADF), because sleep() had closed SPI and
    nothing re-opened it.
    """
    display, panel = panel_display

    first = display._writeToScreen(corner_marked_canvas())
    second = display._writeToScreen(corner_marked_canvas())
    third = display._writeToScreen(corner_marked_canvas())

    assert (first, second, third) == (True, True, True)
    assert panel.display_count == 3


def test_every_write_is_paired_with_a_wake_and_a_sleep(panel_display):
    display, panel = panel_display

    for _ in range(4):
        display._writeToScreen(corner_marked_canvas())

    # One of each per write, plus the constructor's own pair.
    assert panel.init_count == 5
    assert panel.sleep_count == 5
    assert panel.awake is False


def test_a_write_failure_does_not_reach_the_hardware_loop(tmp_path, monkeypatch):
    """
    A panel fault used to surface as a bare "Hardware loop error", which named
    the wrong culprit and took the rest of the cycle with it.
    """
    panel = FakePanel(fail_on_display=True)
    monkeypatch.setattr("display.eink_display.epaper", fake_epaper_for(panel))
    display = EInkDisplay(ConfigManager(str(tmp_path)))

    assert display._writeToScreen(corner_marked_canvas()) is False


def test_a_failed_write_still_leaves_the_panel_asleep(tmp_path, monkeypatch):
    """
    The sleep is in a finally block: without it a failing panel would leak a
    descriptor on every cycle, and the next init() would start from a state it
    does not expect.
    """
    panel = FakePanel(fail_on_display=True)
    monkeypatch.setattr("display.eink_display.epaper", fake_epaper_for(panel))
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    display._throttle_seconds = 0

    display._writeToScreen(corner_marked_canvas())

    assert panel.calls[-1] == "sleep"
    assert panel.awake is False


def test_a_panel_that_will_not_wake_is_skipped_not_written_to(tmp_path, monkeypatch):
    """init() returns -1 when it cannot bring the module up."""
    panel = FakePanel(init_result=-1)
    monkeypatch.setattr("display.eink_display.epaper", fake_epaper_for(panel))
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    display._throttle_seconds = 0
    panel.calls.clear()

    assert display._writeToScreen(corner_marked_canvas()) is False
    assert "display" not in panel.calls


def test_writing_with_no_panel_reports_failure(tmp_path):
    """Off the Pi `_display` is None, and that is not a successful write."""
    display = EInkDisplay(ConfigManager(str(tmp_path)))

    assert display._display is None
    assert display._writeToScreen(corner_marked_canvas()) is False


# --- a failed write must be retried, not remembered -----------------------

def test_a_failed_write_is_not_recorded_as_drawn(tmp_path, monkeypatch):
    """
    _should_update_screen suppresses a repeat of the same state, so recording
    the state after a failed write would turn one bad write into a permanently
    frozen panel.
    """
    from models import StateInformation

    panel = FakePanel(fail_on_display=True)
    monkeypatch.setattr("display.eink_display.epaper", fake_epaper_for(panel))
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    display._throttle_seconds = 0

    state = StateInformation(
        readsb_connected=True, range=50, uptime="1:00:00", daily_seen=3, total_seen=9
    )
    display.write_no_flight(state)

    assert display._last_state is None
    assert display._last_update_time == 0


def test_a_successful_write_is_recorded_and_then_throttled(panel_display):
    from models import StateInformation

    display, panel = panel_display
    state = StateInformation(
        readsb_connected=True, range=50, uptime="1:00:00", daily_seen=3, total_seen=9
    )

    display.write_no_flight(state)
    assert display._last_state == "NO_FLIGHT"
    first_count = panel.display_count

    # The same state again: nothing should reach the panel.
    display.write_no_flight(state)
    assert panel.display_count == first_count


def test_a_retry_after_a_failure_reaches_the_panel(tmp_path, monkeypatch):
    """
    The point of not recording a failure: the next cycle tries again. Here the
    panel recovers between the two attempts.
    """
    from models import StateInformation

    panel = FakePanel(fail_on_display=True)
    monkeypatch.setattr("display.eink_display.epaper", fake_epaper_for(panel))
    display = EInkDisplay(ConfigManager(str(tmp_path)))
    display._throttle_seconds = 0

    state = StateInformation(
        readsb_connected=True, range=50, uptime="1:00:00", daily_seen=3, total_seen=9
    )

    display.write_no_flight(state)
    assert display._last_state is None

    panel._fail_on_display = False
    display.write_no_flight(state)

    assert display._last_state == "NO_FLIGHT"
    assert panel.displayed is not None


def test_a_real_flight_ticket_reaches_a_woken_panel(panel_display):
    """The flight path end to end, through the real drawing code."""
    from models import Aircraft

    display, panel = panel_display

    display.write_flight_data(Aircraft(
        hex="c06a1b",
        flight="ACA465",
        altitude=31000,
        speed=208.9,
        heading=164.17,
        lat=45.1,
        lon=-75.1,
        distance=8.4,
        bearing=210.0,
        origin="YOW",
        destination="YYZ",
    ))

    assert panel.displayed is not None
    assert panel.displayed.size == (800, 480)
    assert panel.calls[-3:] == ["init", "display", "sleep"]
    assert display._last_state is not None
