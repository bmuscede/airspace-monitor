"""
ConfigManager tests.

The config file is nested and every lookup goes through a dotted key, so these
cover the path walking, the defaults merge and the copying — not the Wi-Fi
helpers, which only ever touch /etc on the Pi.
"""

import json

import pytest

from utils.config import ConfigManager, FlattenKeys


def write_config(directory, data):
    path = directory / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_creates_the_default_config_when_there_is_no_file(tmp_path):
    manager = ConfigManager(str(tmp_path))

    written = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert written == manager.defaultConfig
    assert manager.Get("flightaware.cache_ttl") == 3600


def test_dotted_keys_reach_nested_values(tmp_path):
    write_config(tmp_path, {"radar": {"home_lat": 43.65, "home_lon": -79.38}})
    manager = ConfigManager(str(tmp_path))

    assert manager.Get("radar.home_lat") == 43.65
    assert manager.Get("splitflap.auto_rehome.max_attempts") == 3


def test_a_key_without_dots_returns_the_whole_object(tmp_path):
    write_config(tmp_path, {"radar": {"home_lat": 43.65}})
    manager = ConfigManager(str(tmp_path))

    radar = manager.Get("radar")
    assert radar["home_lat"] == 43.65
    # Merged with the defaults, so the keys the file left out are still there.
    assert radar["max_range_nm"] == 50


def test_objects_come_back_as_copies(tmp_path):
    manager = ConfigManager(str(tmp_path))

    manager.Get("radar")["home_lat"] = 99.0
    manager.GetAll()["log_level"] = "DEBUG"

    assert manager.Get("radar.home_lat") == 0.0
    assert manager.Get("log_level") == "INFO"


def test_missing_keys_fall_back_to_the_given_default_then_the_config_default(tmp_path):
    manager = ConfigManager(str(tmp_path))

    assert manager.Get("radar.nothing_here", 7) == 7
    assert manager.Get("radar.nothing_here") is None
    assert manager.Get("nothing.here.at.all", "fallback") == "fallback"
    # No default given: the hardcoded config default answers.
    assert manager.Get("history.retention_days") == 90


def test_set_writes_through_a_dotted_key_and_persists(tmp_path):
    manager = ConfigManager(str(tmp_path))

    manager.Set("radar.home_lat", 43.65)
    manager.Set("splitflap.calibration.calibrated", True)
    assert manager.SaveConfig() is True

    reloaded = ConfigManager(str(tmp_path))
    assert reloaded.Get("radar.home_lat") == 43.65
    assert reloaded.Get("splitflap.calibration.calibrated") is True
    # Setting one key leaves its siblings alone.
    assert reloaded.Get("radar.max_range_nm") == 50


def test_set_creates_the_objects_on_the_way_down(tmp_path):
    manager = ConfigManager(str(tmp_path))

    manager.Set("brand.new.branch", "value")

    assert manager.Get("brand") == {"new": {"branch": "value"}}
    assert manager.Get("brand.new.branch") == "value"


def test_set_refuses_to_bury_a_scalar(tmp_path):
    manager = ConfigManager(str(tmp_path))

    with pytest.raises(ValueError):
        manager.Set("log_level.nested", "nope")

    with pytest.raises(ValueError):
        manager.Set("", "nope")


def test_loading_merges_nested_objects_rather_than_replacing_them(tmp_path):
    # A config written before splitflap.calibration existed.
    write_config(tmp_path, {"splitflap": {"enabled": True, "channels": [0, 1]}})
    manager = ConfigManager(str(tmp_path))

    assert manager.Get("splitflap.enabled") is True
    assert manager.Get("splitflap.channels") == [0, 1]
    assert manager.Get("splitflap.calibration.calibrated") is False
    assert "default" in manager.Get("splitflap.charsets")


def test_has_knows_the_config_and_the_defaults(tmp_path):
    manager = ConfigManager(str(tmp_path))

    assert manager.Has("radar.home_lat")
    assert manager.Has("radar")
    assert not manager.Has("radar.home_latitude")
    assert not manager.Has("")


def test_a_broken_config_file_falls_back_to_the_defaults(tmp_path):
    (tmp_path / "config.json").write_text("{not json", encoding="utf-8")
    manager = ConfigManager(str(tmp_path))

    assert manager.GetAll() == manager.defaultConfig


def test_flatten_keys_turns_a_payload_into_dotted_keys():
    flat = FlattenKeys({
        "radar": {"home_lat": 43.65, "max_range_nm": 60},
        "log_level": "DEBUG",
        "splitflap": {"channels": [0, 1], "charsets": {}},
    })

    assert flat == {
        "radar.home_lat": 43.65,
        "radar.max_range_nm": 60,
        "log_level": "DEBUG",
        "splitflap.channels": [0, 1],
        "splitflap.charsets": {},
    }
