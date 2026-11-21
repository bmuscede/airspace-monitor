"""
E-Ink orientation tests.

The case in this repo holds the panel upside down, so the driver turns the
finished image 180 degrees on its way to the hardware. The drawing code above
it stays in reading order, which means this one step is the only thing standing
between a correct layout and an unreadable screen — worth pinning down.

These run without a panel: `epaper` is absent off the Pi, so the constructor
falls back to its 800x480 software size and `_display` is None. A fake panel is
injected where the write path is under test.
"""

import json

from PIL import Image

from display.eink_display import EInkDisplay
from utils.config import ConfigManager


class FakePanel:
    """Stands in for the Waveshare EPD, recording what it was handed."""

    def __init__(self):
        self.width = 800
        self.height = 480
        self.displayed = None
        self.buffered = None
        self.slept = False

    def getbuffer(self, image):
        # The real driver returns a packed byte buffer. The image itself is
        # what these tests care about, so it is passed straight through.
        self.buffered = image
        return image

    def display(self, buffer):
        self.displayed = buffer

    def sleep(self):
        self.slept = True


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
