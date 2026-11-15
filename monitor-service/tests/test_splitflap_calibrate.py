"""
Calibration tool tests.

The tool is interactive and talks to hardware, so both are faked: a stub display that records
the commands it was given, and a scripted stand-in for input(). What is worth pinning down is
the procedure itself — a builder runs it once, in a workshop, and a wrong turn costs them a
pass over every module — and that a finished calibration is recorded where the service looks.
"""

import json

import pytest

from splitflap import calibrate as tool
from splitflap.config import SplitFlapCharset
from splitflap.protocol import ModuleState
from utils.config import ConfigManager

FLAPS = ["A", "B", "C", "D"]


class FakeModule:
    def __init__(self, state=ModuleState.NORMAL):
        self.state = state
        self.channel = 0
        self.position = 0
        self.flap_index = 0
        self.token = "A"
        self.moving = False
        self.home_sensor = True
        self.missed_home = 0
        self.unexpected_home = 0


class FakePosition:
    def __init__(self, charset, channel=0):
        self.channel = channel
        self.charset = charset


class FakeConfig:
    def __init__(self, charset, channels=(0,)):
        self.positions = [FakePosition(charset, ch) for ch in channels]


class FakeDisplay:
    """Records what the procedure asked the modules to do."""

    def __init__(self, state=ModuleState.NORMAL, save_reply="SUCCESS - saved calibration!",
                 flaps=FLAPS, channels=(0,), states=None):
        self.charset_ = SplitFlapCharset("test", flaps)
        self.config = FakeConfig(self.charset_, channels)
        self.num_positions = len(channels)
        self.calls = []
        self._modules = [FakeModule(s) for s in (states or [state] * len(channels))]
        self._on_log = None
        self._save_reply = save_reply
        self.closed = False

    def charset(self, position):
        return self.charset_

    def status_of(self, position):
        return self._modules[position]

    def close(self):
        self.closed = True

    def rehome(self, positions=None):
        self.calls.append(("rehome", positions))

    def wait_until_idle(self, positions=None, timeout=60.0):
        return True

    def go_to_index(self, position, index, force_rotation=False):
        self.calls.append(("go_to_index", index))

    def nudge_offset(self, position, half=False):
        self.calls.append(("nudge_half" if half else "nudge", position))

    def set_offset_here(self, position):
        self.calls.append(("set_offset_here", position))

    def add_log_listener(self, callback):
        self._on_log = callback
        return lambda: None

    def save_calibration(self):
        self.calls.append(("save", None))
        if self._save_reply is not None:
            self._on_log(self._save_reply)


@pytest.fixture
def answers(monkeypatch):
    """Scripts input(). Each call takes the next answer."""
    scripted = []

    def feed(*values):
        scripted.extend(values)

    def fake_input(prompt=""):
        if not scripted:
            raise AssertionError(f"the tool asked something the test didn't answer: {prompt!r}")
        return scripted.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)
    return feed


def test_calibrating_a_module_nudges_then_sets_the_offset_where_the_flaps_line_up(answers):
    display = FakeDisplay()
    # A flap falls after two nudges, C is showing, and both checks look right.
    answers("", "", "f", "C", "", "")

    assert tool.calibrate_position(display, 0) is True
    assert display.calls == [
        ("go_to_index", 0),
        ("nudge", 0),
        ("nudge", 0),
        ("nudge_half", 0),
        # C is two flaps before home in a four-flap charset, so turn two to bring A back.
        ("go_to_index", 2),
        ("set_offset_here", 0),
        ("rehome", [0]),
    ]


def test_a_module_can_be_skipped(answers):
    display = FakeDisplay()
    answers("s")

    assert tool.calibrate_position(display, 0) is False
    assert ("set_offset_here", 0) not in display.calls


def test_a_flap_that_is_not_on_the_spool_is_asked_again(answers):
    display = FakeDisplay()
    answers("f", "Z", "C", "", "")

    assert tool.calibrate_position(display, 0) is True


def test_a_module_that_still_cannot_find_home_is_skipped(answers):
    display = FakeDisplay(state=ModuleState.SENSOR_ERROR)

    assert tool.calibrate_position(display, 0) is False
    assert ("rehome", [0]) in display.calls


def test_a_no_at_the_last_check_starts_the_module_again(answers):
    display = FakeDisplay()
    # First pass looks wrong at step 4, second pass is accepted.
    answers("f", "C", "", "n", "f", "C", "", "")

    assert tool.calibrate_position(display, 0) is True
    assert [c for c in display.calls if c[0] == "set_offset_here"] == [("set_offset_here", 0)] * 2


def test_saving_returns_the_firmwares_reply():
    display = FakeDisplay()

    assert tool.save_offsets(display) == "SUCCESS - saved calibration!"
    assert ("save", None) in display.calls


def test_a_silent_firmware_is_reported_rather_than_assumed_saved():
    display = FakeDisplay(save_reply=None)

    assert tool.save_offsets(display, timeout=0.05) is None


def test_a_finished_calibration_is_recorded_for_the_service(tmp_path):
    tool.record_calibration(str(tmp_path), True)

    manager = ConfigManager(str(tmp_path))
    assert manager.Get("splitflap.calibration.calibrated") is True
    assert manager.Get("splitflap.calibration.calibrated_at") > 0


def test_forget_makes_the_service_calibrate_again(tmp_path):
    tool.record_calibration(str(tmp_path), True)

    assert tool.cmd_forget(_Args(config_dir=str(tmp_path))) == 0

    manager = ConfigManager(str(tmp_path))
    assert manager.Get("splitflap.calibration.calibrated") is False
    assert manager.Get("splitflap.calibration.calibrated_at") == 0.0


def test_a_display_with_no_channels_is_a_clear_error_rather_than_a_traceback(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"splitflap": {"channels": []}}), encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        tool.open_driver(_Args(config_dir=str(tmp_path), port=None))

    assert "no channels" in str(excinfo.value)


class _Args:
    """Stands in for the parsed command line."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


def test_a_logo_flap_is_typed_the_way_the_tool_prints_it(answers):
    # The tool prints logo flaps as {ACA} everywhere, the list it offers when it rejects an
    # answer included, so that is what has to be accepted back.
    display = FakeDisplay(flaps=[" ", "A", "ACA", "WJA"])
    answers("f", "{ACA}", "", "")

    assert tool.calibrate_position(display, 0) is True
    # ACA is flap 2 of 4, so two more flaps bring the blank home flap back round.
    assert ("go_to_index", 2) in display.calls


def test_a_logo_flap_typed_without_its_braces_is_counted_and_asked_again(answers, capsys):
    display = FakeDisplay(flaps=[" ", "A", "ACA", "WJA"])
    answers("f", "ACA", "{ACA}", "", "")

    assert tool.calibrate_position(display, 0) is True
    out = capsys.readouterr().out
    assert "'ACA' is 3 flaps" in out
    assert "{ACA}" in out


def test_an_unclosed_brace_is_reported_rather_than_ending_the_run(answers, capsys):
    display = FakeDisplay(flaps=[" ", "A", "ACA"])
    answers("f", "{ACA", "{ACA}", "", "")

    assert tool.calibrate_position(display, 0) is True
    assert "unclosed" in capsys.readouterr().out


def test_the_tool_never_re_homes_a_module_behind_the_builders_back(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({
        "splitflap": {"channels": [0, 1], "auto_rehome": {"enabled": True}},
    }), encoding="utf-8")
    seen = {}

    class StubDriver:
        def __init__(self, config, port=None):
            seen["config"] = config

        def open(self):
            return self

        def wait_connected(self, timeout=10.0):
            return True

    monkeypatch.setattr(tool, "SplitFlapDriver", StubDriver)
    tool.open_driver(_Args(config_dir=str(tmp_path), port=None))

    # The service heals a module that loses home by re-homing it in the background. Here that
    # would move the module between "which flap is showing?" and the builder's answer.
    assert seen["config"].auto_rehome is False


def test_a_run_that_skips_a_module_says_which_one_and_what_is_left(tmp_path, monkeypatch, answers, capsys):
    # The channels a real build uses aren't contiguous, so a skipped module looks like the
    # run jumping to a channel further along for no reason. It has to say so.
    display = FakeDisplay(channels=(0, 4, 6),
                          states=[ModuleState.NORMAL, ModuleState.SENSOR_ERROR, ModuleState.NORMAL])
    monkeypatch.setattr(tool, "open_driver", lambda args: display)
    monkeypatch.setattr(tool, "require_matching_flaps", lambda display: None)
    answers("f", "C", "", "", "f", "C", "", "")

    assert tool.cmd_calibrate(_Args(config_dir=str(tmp_path), port=None, positions=[])) == 0

    out = capsys.readouterr().out
    assert "position 1 (channel 4)" in out
    assert "Still not calibrated: 1" in out
    assert display.closed
