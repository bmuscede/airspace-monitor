"""
SplitFlapConfig tests.

The config file and the driver describe the display differently — channels against positions,
seconds against suffixed names — and this is where the two meet, so these cover the translation
and what it does with a file someone has filled in wrongly.
"""

import pytest

from splitflap.config import (
    LEGACY_40_FLAPS,
    SplitFlapCharset,
    SplitFlapConfig,
    parse_tokens,
    token_label,
)

FLAPS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!?."


def section(**overrides):
    data = {
        "channels": [{"channel": i, "charset": "default"} for i in range(4)],
        "charsets": {"default": {"flaps": FLAPS}},
    }
    data.update(overrides)
    return data


def test_the_config_file_describes_the_display():
    config = SplitFlapConfig.from_service_section(section(
        port="/dev/ttyUSB0",
        rows=[2, 2],
        auto_rehome={"enabled": False, "max_attempts": 5, "window_seconds": 42, "backoff_seconds": 7},
    ))

    assert [p.channel for p in config.positions] == [0, 1, 2, 3]
    assert config.port == "/dev/ttyUSB0"
    assert config.auto_rehome is False
    assert config.max_rehome_attempts == 5
    # The file says seconds; the driver wants its own names.
    assert (config.rehome_window_s, config.rehome_backoff_s) == (42.0, 7.0)


def test_an_empty_section_is_an_empty_display_rather_than_an_error():
    config = SplitFlapConfig.from_service_section({})

    assert config.positions == []
    assert config.port is None
    assert config.row_spans() == [(0, 0)]


def test_rows_divide_the_channels_top_to_bottom():
    config = SplitFlapConfig.from_service_section(section(rows=[1, 3]))

    assert config.row_spans() == [(0, 1), (1, 3)]


def test_no_rows_means_one_row_of_everything():
    config = SplitFlapConfig.from_service_section(section())

    assert config.row_spans() == [(0, 4)]


@pytest.mark.parametrize("rows", [[5], [2, 3], [0, 4], [-1], ["two"], [2.5]])
def test_rows_that_do_not_fit_fall_back_to_one_row(rows):
    config = SplitFlapConfig.from_service_section(section(rows=rows))

    assert config.row_spans() == [(0, 4)]


def test_channels_can_be_bare_numbers_and_get_the_default_charset():
    config = SplitFlapConfig.from_service_section({"channels": [0, 4, 11]})

    assert [p.channel for p in config.positions] == [0, 4, 11]
    assert [p.charset.flaps for p in config.positions] == [tuple(LEGACY_40_FLAPS)] * 3


def test_a_channel_cannot_hold_two_positions():
    with pytest.raises(ValueError, match="only be used by one position"):
        SplitFlapConfig.from_service_section({"channels": [3, 3]})


def test_an_unknown_charset_names_the_position_that_asked_for_it():
    with pytest.raises(ValueError, match="position 1: unknown charset 'logos'"):
        SplitFlapConfig.from_service_section(section(channels=[
            {"channel": 0, "charset": "default"},
            {"channel": 1, "charset": "logos"},
        ]))


def test_a_logo_charset_can_alias_an_airline_onto_a_flap_it_has():
    config = SplitFlapConfig.from_service_section({
        "channels": [{"channel": 0, "charset": "logos"}],
        "charsets": {"logos": {"flaps": [" ", "ACA", "WJA"], "aliases": {"ROU": "ACA"}}},
    })
    charset = config.positions[0].charset

    assert charset.lookup("ACA") == 1
    assert charset.lookup("ROU") == 1
    # Not on this spool: the blank flap stands in, rather than the module moving.
    assert charset.lookup("DAL") is None
    assert charset.resolve("DAL") == 0


def test_a_charset_cannot_promise_a_fallback_it_does_not_have():
    with pytest.raises(ValueError, match="fallback"):
        SplitFlapCharset("logos", ["ACA", "WJA"], fallback="DAL")


def test_text_splits_into_flaps_with_logos_named_in_braces():
    assert parse_tokens("{ACA}857") == ["ACA", "8", "5", "7"]
    assert parse_tokens("A{{B}}") == ["A", "{", "B", "}"]

    with pytest.raises(ValueError, match="unclosed"):
        parse_tokens("{ACA")


def test_flaps_are_labelled_so_a_log_line_can_be_read():
    assert token_label("A") == "A"
    assert token_label(" ") == "(blank)"
    assert token_label("ACA") == "{ACA}"
    assert token_label(None) == "?"


def test_a_spool_written_as_text_keeps_its_logo_flaps_whole():
    # The config file's own "flight" set: 26 letters, a blank, 12 logos and a '#' is 40 flaps,
    # not the 87 characters it takes to write them down.
    config = SplitFlapConfig.from_service_section({
        "channels": [{"channel": 0, "charset": "flight"}],
        "charsets": {"flight": {"flaps": " ABCDEFGHIJKLMNOPQRSTUVWXYZ{GA}{ACA}{WJT}{FLE}"
                                         "{UAL}{POE}{TSC}{DAL}{AAL}{SWA}{UPS}{FDX}#"}},
    })
    charset = config.positions[0].charset

    assert len(charset) == 40
    assert charset.flaps[27] == "GA"
    assert charset.lookup("ACA") == 28
    assert charset.token(28) == "ACA"
    # The braces are punctuation in the file, so they are not flaps on the spool.
    assert charset.lookup("{") is None


def test_a_spool_can_hold_a_brace_flap_by_doubling_it():
    charset = SplitFlapCharset("braces", " AB{{}}{ACA}")

    assert charset.flaps == (" ", "A", "B", "{", "}", "ACA")


def test_a_spool_given_as_a_list_is_already_one_flap_per_entry():
    # Each entry is one flap however long it is, which is the form the dashboard writes.
    charset = SplitFlapCharset("logos", [" ", "A", "ACA"])

    assert charset.flaps == (" ", "A", "ACA")
    assert len(charset) == 3


def test_a_fallback_and_an_alias_name_one_flap_so_they_take_the_bare_token():
    # Braces delimit flaps that run together in text. These settings hold exactly one
    # flap each, so there is nothing to delimit and the token stands on its own.
    charset = SplitFlapCharset("logos", " {ACA}", aliases={"ROU": "ACA"}, fallback="ACA")

    assert charset.fallback == "ACA"
    assert charset.lookup("ROU") == 1
    # Nothing on this spool, so the fallback flap stands in.
    assert charset.resolve("DAL") == 1


def test_a_fallback_that_is_not_a_flap_names_the_charset_and_the_value():
    with pytest.raises(ValueError, match=r"charset 'logos': fallback 'AC' isn't one of its flaps"):
        SplitFlapCharset("logos", " {ACA}", fallback="AC")

    with pytest.raises(ValueError, match=r"alias 'ROU' points at 'AC', which isn't one of its flaps"):
        SplitFlapCharset("logos", " {ACA}", aliases={"ROU": "AC"})


def test_charsets_of_different_lengths_are_warned_about_rather_than_refused(caplog):
    config = SplitFlapConfig.from_service_section(section(
        channels=[{"channel": 0, "charset": "default"}, {"channel": 1, "charset": "short"}],
        charsets={"default": {"flaps": FLAPS}, "short": {"flaps": [" ", "ACA"]}},
    ))

    assert [len(p.charset) for p in config.positions] == [40, 2]
    assert "NUM_FLAPS" in caplog.text


def test_an_unclosed_brace_names_the_charset_it_was_written_in():
    with pytest.raises(ValueError, match="charset 'flight': unclosed"):
        SplitFlapCharset("flight", " AB{ACA")
