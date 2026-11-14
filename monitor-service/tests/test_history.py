"""
HistoryStore tests.

Unlike the tracker these do touch a database — that is the point of the class.
They use a real SQLite file in a tmp_path, never a mock.
"""

import sqlite3
import time

import pytest

from controller.tracker import ContactTracker
from data.history import HistoryStore
from models import UNKNOWN, Aircraft


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
def db_path(tmp_path):
    return str(tmp_path / "history.db")


@pytest.fixture
def wired(db_path):
    """A tracker with a HistoryStore subscribed, as the controller wires them."""
    tracker = ContactTracker(contact_gap_seconds=300)
    store = HistoryStore(db_path=db_path, flush_seconds=300, retention_days=90,
                         contacts_provider=lambda: tracker.contacts)
    tracker.subscribe(store.handle_event)
    yield tracker, store
    store.Close()


def rows(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in connection.execute("SELECT * FROM contacts ORDER BY id")]
    finally:
        connection.close()


# --- Write policy ---------------------------------------------------------

def test_nothing_is_written_while_a_contact_is_live(wired, db_path):
    tracker, _ = wired
    for i in range(20):
        tracker.update([make_aircraft("abc123", distance=20.0 - i)], now=1000.0 + i * 2)

    assert rows(db_path) == []


def test_exactly_one_row_per_visit(wired, db_path):
    tracker, _ = wired
    # Twenty sweeps, then a departure. One row, not twenty.
    for i in range(20):
        tracker.update([make_aircraft("abc123", flight="ACA123", distance=20.0 - i)], now=1000.0 + i * 2)
    tracker.update([], now=1000.0 + 400)

    written = rows(db_path)
    assert len(written) == 1
    assert written[0]["hex"] == "abc123"
    assert written[0]["flight"] == "ACA123"
    assert written[0]["sample_count"] == 20
    assert written[0]["closest_nm"] == 1.0
    assert written[0]["closed"] == 1


def test_a_second_visit_is_a_second_row(wired, db_path):
    tracker, _ = wired
    tracker.update([make_aircraft("abc123")], now=1000.0)
    tracker.update([], now=1400.0)
    tracker.update([make_aircraft("abc123")], now=2000.0)
    tracker.update([], now=2400.0)

    assert len(rows(db_path)) == 2


def test_backstop_flush_writes_open_contacts_then_close_updates_them(wired, db_path):
    tracker, store = wired
    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1000.0)

    store.Flush()
    flushed = rows(db_path)
    assert len(flushed) == 1
    assert flushed[0]["closed"] == 0

    tracker.update([], now=1400.0)
    closed = rows(db_path)
    # Updated in place, not duplicated.
    assert len(closed) == 1
    assert closed[0]["id"] == flushed[0]["id"]
    assert closed[0]["closed"] == 1


def test_unknown_identity_is_stored_as_null(wired, db_path):
    tracker, _ = wired
    tracker.update([make_aircraft("abc123")], now=1000.0)
    tracker.update([], now=1400.0)

    assert rows(db_path)[0]["flight"] is None


# --- Unclean shutdown -----------------------------------------------------

def test_orphaned_open_rows_are_reconciled_on_startup(db_path):
    tracker = ContactTracker(contact_gap_seconds=300)
    store = HistoryStore(db_path=db_path, contacts_provider=lambda: tracker.contacts)
    tracker.subscribe(store.handle_event)

    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1000.0)
    store.Flush()
    # Simulate SIGKILL: drop the connection without closing contacts.
    store.Close()

    assert rows(db_path)[0]["closed"] == 0

    reopened = HistoryStore(db_path=db_path)
    try:
        assert rows(db_path)[0]["closed"] == 1
    finally:
        reopened.Close()


def test_clean_shutdown_flushes_open_contacts(wired, db_path):
    tracker, _ = wired
    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1000.0)
    tracker.update([make_aircraft("abc123", flight="ACA123")], now=1002.0)

    # What Controller._finalize() does.
    tracker.close_all(now=1004.0)

    written = rows(db_path)
    assert len(written) == 1
    assert written[0]["closed"] == 1
    assert written[0]["sample_count"] == 2


# --- Counters -------------------------------------------------------------

def test_counters_survive_a_restart(db_path):
    """The headline bug: total_seen used to reset to zero on every restart."""
    tracker = ContactTracker(contact_gap_seconds=300)
    store = HistoryStore(db_path=db_path, contacts_provider=lambda: tracker.contacts)
    tracker.subscribe(store.handle_event)

    now = time.time()
    tracker.update(
        [make_aircraft("aaa111"), make_aircraft("bbb222"), make_aircraft("ccc333")],
        now=now,
    )
    tracker.close_all(now=now + 1)

    assert store.daily_seen == 3
    assert store.total_seen == 3
    assert store.distinct_aircraft_ever == 3
    store.Close()

    # Restart: brand new tracker and store against the same file.
    restarted = HistoryStore(db_path=db_path)
    try:
        assert restarted.daily_seen == 3
        assert restarted.total_seen == 3
        assert restarted.distinct_aircraft_ever == 3
    finally:
        restarted.Close()


def test_total_seen_counts_an_aircraft_once_per_day(db_path):
    """
    total_seen is the sum of daily uniques, matching the old in-memory
    behaviour: a daily commuter flight counts once per day, not once ever.
    distinct_aircraft_ever is the one that counts it once.
    """
    store = HistoryStore(db_path=db_path)
    now = time.time()
    connection = sqlite3.connect(db_path)
    try:
        for offset in (0, 86400, 2 * 86400):
            connection.execute(
                "INSERT INTO contacts (hex, first_seen, last_seen, closest_nm, sample_count, closed)"
                " VALUES (?, ?, ?, ?, ?, 1)",
                ("aaa111", now - offset, now - offset + 60, 5.0, 10),
            )
        connection.commit()
    finally:
        connection.close()

    store._invalidate_counters()
    assert store.total_seen == 3
    assert store.distinct_aircraft_ever == 1
    store.Close()


def test_counter_cache_is_invalidated_on_close(wired):
    tracker, store = wired
    now = time.time()

    assert store.daily_seen == 0

    tracker.update([make_aircraft("abc123")], now=now)
    tracker.close_all(now=now + 1)

    # Would still read 0 from a stale cache.
    assert store.daily_seen == 1


# --- Queries --------------------------------------------------------------

def test_contacts_are_keyset_paginated_newest_first(wired, db_path):
    tracker, store = wired
    now = time.time()
    for i in range(5):
        tracker.update([make_aircraft(f"ac{i}")], now=now + i)
        tracker.update([], now=now + i + 400)

    first = store.GetContacts(limit=2)
    assert len(first["contacts"]) == 2
    assert first["next_before"] is not None

    second = store.GetContacts(
        before=first["next_before"], before_id=first["next_before_id"], limit=2
    )
    assert len(second["contacts"]) == 2

    ids = [c["id"] for c in first["contacts"] + second["contacts"]]
    assert len(set(ids)) == 4, "keyset pagination repeated a row"

    last_seens = [c["last_seen"] for c in first["contacts"] + second["contacts"]]
    assert last_seens == sorted(last_seens, reverse=True)


def test_stats_are_computed_in_sql(wired):
    tracker, store = wired
    now = time.time()
    tracker.update(
        [
            make_aircraft("aaa111", flight="ACA111", distance=12.0),
            make_aircraft("bbb222", flight="ACA222", distance=3.4),
        ],
        now=now,
    )
    tracker.close_all(now=now + 1)

    stats = store.GetStats("today")
    assert stats["contact_count"] == 2
    assert stats["distinct_aircraft"] == 2
    assert stats["closest_nm"] == 3.4
    assert stats["closest_hex"] == "bbb222"
    assert stats["closest_flight"] == "ACA222"
    assert stats["busiest_hour"] is not None


# --- Retention ------------------------------------------------------------

def seed(db_path, hex_code, when, closest=5.0):
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO contacts (hex, first_seen, last_seen, closest_nm, sample_count, closed)"
            " VALUES (?, ?, ?, ?, 10, 1)",
            (hex_code, when, when + 120, closest),
        )
        connection.commit()
    finally:
        connection.close()


def test_retention_rolls_old_contacts_into_daily_stats(db_path):
    store = HistoryStore(db_path=db_path, retention_days=90)
    now = time.time()
    old = now - 120 * 86400
    recent = now - 10 * 86400

    seed(db_path, "old111", old, closest=4.0)
    seed(db_path, "old222", old, closest=9.0)
    seed(db_path, "new333", recent, closest=6.0)
    store._invalidate_counters()

    store._run_retention(now)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        remaining = [dict(r) for r in connection.execute("SELECT hex FROM contacts")]
        daily = [dict(r) for r in connection.execute("SELECT * FROM daily_stats")]
    finally:
        connection.close()

    assert [r["hex"] for r in remaining] == ["new333"]
    assert len(daily) == 1
    assert daily[0]["contact_count"] == 2
    assert daily[0]["unique_aircraft"] == 2
    assert daily[0]["closest_nm"] == 4.0
    assert daily[0]["closest_hex"] == "old111"
    store.Close()


def test_total_seen_spans_rolled_and_retained_days(db_path):
    """
    After retention, part of the history lives in daily_stats and part still
    lives in contacts. total_seen has to cover both without double-counting.
    """
    store = HistoryStore(db_path=db_path, retention_days=90)
    now = time.time()
    seed(db_path, "old111", now - 120 * 86400)
    seed(db_path, "old222", now - 120 * 86400)
    seed(db_path, "new333", now - 10 * 86400)
    seed(db_path, "new444", now)
    store._invalidate_counters()

    assert store.total_seen == 4

    store._run_retention(now)
    store._invalidate_counters()

    # 2 rolled into daily_stats + 2 still in contacts.
    assert store.total_seen == 4
    assert store.distinct_aircraft_ever == 2, "rolled-off days keep counts, not identities"
    store.Close()


def test_stats_range_all_includes_everything(wired):
    tracker, store = wired
    old = time.time() - 30 * 86400
    tracker.update([make_aircraft("old111")], now=old)
    tracker.close_all(now=old + 1)

    assert store.GetStats("today")["contact_count"] == 0
    assert store.GetStats("all")["contact_count"] == 1
