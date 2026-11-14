import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from models import Contact, ContactClosed, TrackerEvent, UNKNOWN
from utils.logs import GetLogger

SCHEMA_VERSION = 1

DEFAULT_FLUSH_SECONDS = 300
DEFAULT_RETENTION_DAYS = 90

# How stale the E-Ink counters may get. _push_to_display asks for these on
# every hardware cycle, so they must never become a SQL query on that path.
COUNTER_CACHE_SECONDS = 60

# Retention runs at most this often, and never on the write path.
RETENTION_INTERVAL_SECONDS = 24 * 60 * 60

SCHEMA_STATEMENTS = [
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)",
    """
    CREATE TABLE IF NOT EXISTS contacts (
        id              INTEGER PRIMARY KEY,
        hex             TEXT    NOT NULL,
        flight          TEXT,
        registration    TEXT,
        aircraft_type   TEXT,
        origin          TEXT,
        destination     TEXT,
        first_seen      REAL    NOT NULL,
        last_seen       REAL    NOT NULL,
        closest_nm      REAL    NOT NULL,
        closest_at      REAL,
        closest_bearing REAL,
        min_altitude    INTEGER,
        max_altitude    INTEGER,
        max_speed       INTEGER,
        sample_count    INTEGER NOT NULL DEFAULT 0,
        closed          INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_contacts_last_seen  ON contacts(last_seen DESC)",
    "CREATE INDEX IF NOT EXISTS idx_contacts_first_seen ON contacts(first_seen)",
    "CREATE INDEX IF NOT EXISTS idx_contacts_hex        ON contacts(hex)",
    """
    CREATE TABLE IF NOT EXISTS daily_stats (
        day             TEXT PRIMARY KEY,
        contact_count   INTEGER NOT NULL,
        unique_aircraft INTEGER NOT NULL,
        closest_nm      REAL,
        closest_hex     TEXT
    )
    """,
]

# SQLite has no notion of our local timezone beyond the 'localtime' modifier,
# so day bucketing is expressed once here and reused everywhere.
LOCAL_DAY = "date(%s, 'unixepoch', 'localtime')"


class HistoryStore:
    """
    SQLite persistence for completed contacts.

    The write policy is the whole point: **a contact is only worth writing once,
    when it closes.** While an aircraft is in range everything we care about is
    still changing, so repeated writes would just burn the SD card we are
    trying to protect. That is roughly one insert per aircraft per visit — a few
    hundred a day, against the ~864,000 we would get logging every 2s sweep.

    A backstop flush writes still-open contacts with closed = 0 every
    `flush_seconds` so a power cut costs minutes rather than hours. Anything
    still marked closed = 0 at startup is an orphan from an unclean shutdown and
    gets reconciled to closed = 1: those records are as complete as they will
    ever be.

    Subscribes to ContactTracker events; the tracker knows nothing about this
    class and holds no database handle.
    """

    def __init__(
        self,
        db_path: str,
        flush_seconds: int = DEFAULT_FLUSH_SECONDS,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        contacts_provider: Optional[Callable[[], List[Contact]]] = None,
        logger=None,
    ):
        self.logger = logger if logger is not None else GetLogger("HistoryStore")

        self.db_path = db_path
        self.flush_seconds = flush_seconds
        self.retention_days = retention_days

        # Supplies the currently-open contacts for the backstop flush. Injected
        # rather than reached for, so the flush policy stays here while the
        # tracker stays unaware of us. Only invoked when a flush is actually due.
        self._contacts_provider = contacts_provider

        # Single writer, owned by the hardware thread, guarded by a lock. The
        # connection is created lazily on the first write so it binds to
        # whichever thread actually runs the hardware loop, rather than to
        # whichever thread happened to construct the Controller. SQLite
        # connections are thread-affine and getting that wrong fails every
        # write with a logged error rather than anything louder.
        self._write_lock = threading.RLock()
        self._writer: Optional[sqlite3.Connection] = None
        self._writer_thread: Optional[threading.Thread] = None

        # Readers get their own connection. Sharing one with
        # check_same_thread=False would serialise API reads behind hardware
        # writes and corrupt cursor state under concurrency.
        self._readers = threading.local()

        # (hex, first_seen) -> rowid, so a backstop-flushed contact is updated
        # on close rather than duplicated. Deliberately *not* an id on the
        # Contact model: that would leak persistence back into the tracker.
        self._open_rows: Dict[Tuple[str, float], int] = {}

        self._counter_cache: Optional[Dict[str, int]] = None
        self._counter_cache_at = 0.0

        self._last_flush = time.time()
        self._last_retention = 0.0
        self._closed = False

        directory = os.path.dirname(os.path.abspath(self.db_path))
        if directory:
            os.makedirs(directory, exist_ok=True)

        self._initialise()

    # --- Setup ---

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        # WAL is chosen so API reads can proceed concurrently with
        # hardware-thread writes; the reduced write amplification is a bonus,
        # not the reason.
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialise(self) -> None:
        """
        Creates the schema and reconciles orphans, on a throwaway connection so
        we do not bind the writer to the constructing thread.
        """
        connection = self._connect()
        try:
            with connection:
                for statement in SCHEMA_STATEMENTS:
                    connection.execute(statement)

                row = connection.execute("SELECT version FROM schema_version").fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
                    )

                # Reconcile orphans from an unclean shutdown. Turns a power cut
                # from data loss into slightly-truncated records, for free.
                cursor = connection.execute(
                    "UPDATE contacts SET closed = 1 WHERE closed = 0"
                )
                orphans = cursor.rowcount
        finally:
            connection.close()

        if orphans > 0:
            self.logger.warning(
                f"Reconciled {orphans} contact(s) left open by an unclean shutdown."
            )
        self.logger.info(f"History store ready at {self.db_path}.")

    def _writer_connection(self) -> sqlite3.Connection:
        """The single write connection. Call only under _write_lock."""
        if self._writer is None:
            self._writer = self._connect()
            self._writer_thread = threading.current_thread()
        return self._writer

    def _reader(self) -> sqlite3.Connection:
        connection = getattr(self._readers, "connection", None)
        if connection is None:
            connection = self._connect()
            self._readers.connection = connection
        return connection

    # --- Tracker subscription ---

    def handle_event(self, event: TrackerEvent) -> None:
        """
        Tracker event handler. Register with tracker.subscribe().

        Only ContactClosed touches the disk. Opens and updates are ignored on
        purpose — live tracks stay in the tracker's memory at zero I/O cost.
        """
        if isinstance(event, ContactClosed):
            self._write_closed(event.contact)

    # --- Writes ---

    def _write_closed(self, contact: Contact) -> None:
        if self._closed:
            return
        key = (contact.hex, contact.first_seen)
        try:
            with self._write_lock:
                writer = self._writer_connection()
                rowid = self._open_rows.pop(key, None)
                with writer:
                    if rowid is not None:
                        writer.execute(
                            _UPDATE_SQL, _contact_values(contact, closed=1) + (rowid,)
                        )
                    else:
                        writer.execute(_INSERT_SQL, _contact_values(contact, closed=1))
            self._invalidate_counters()
        except Exception as e:
            self.logger.error(f"Failed to persist contact {contact.hex}: {e}")

    def Flush(self, contacts: Optional[List[Contact]] = None) -> int:
        """
        Backstop flush: writes currently-open contacts with closed = 0 in a
        single transaction. Losing a few minutes of open contacts to a power
        cut is acceptable; losing hours is not.
        """
        if self._closed:
            return 0
        if contacts is None:
            if self._contacts_provider is None:
                return 0
            contacts = self._contacts_provider()
        if not contacts:
            return 0

        try:
            with self._write_lock:
                writer = self._writer_connection()
                with writer:
                    for contact in contacts:
                        key = (contact.hex, contact.first_seen)
                        rowid = self._open_rows.get(key)
                        values = _contact_values(contact, closed=0)
                        if rowid is not None:
                            writer.execute(_UPDATE_SQL, values + (rowid,))
                        else:
                            cursor = writer.execute(_INSERT_SQL, values)
                            self._open_rows[key] = cursor.lastrowid
            self._invalidate_counters()
            return len(contacts)
        except Exception as e:
            self.logger.error(f"Backstop flush failed: {e}")
            return 0

    def Tick(self, now: Optional[float] = None) -> None:
        """
        Housekeeping hook, called once per hardware cycle. Cheap: two timestamp
        comparisons unless a flush or the daily retention pass is actually due.
        """
        if self._closed:
            return
        now = time.time() if now is None else now

        if now - self._last_flush >= self.flush_seconds:
            self._last_flush = now
            written = self.Flush()
            if written:
                self.logger.debug(f"Backstop flush wrote {written} open contact(s).")

        if now - self._last_retention >= RETENTION_INTERVAL_SECONDS:
            self._last_retention = now
            self._run_retention(now)

    def Close(self) -> None:
        """
        Closes the writer connection. Idempotent.

        Must be called from the thread that performed the writes — which is the
        hardware thread, since that is where Controller._finalize() runs.
        """
        with self._write_lock:
            if self._closed:
                return
            self._closed = True
            if self._writer is not None:
                if self._writer_thread is not threading.current_thread():
                    self.logger.warning(
                        "History store closed from a thread that did not own the "
                        "writer; leaving the connection to be reclaimed by exit."
                    )
                else:
                    try:
                        self._writer.close()
                    except Exception as e:
                        self.logger.error(f"Error closing history database: {e}")
                self._writer = None
                self._writer_thread = None
        self.logger.info("History store closed.")

    # --- Retention ---

    def _run_retention(self, now: float) -> None:
        """
        Rolls contacts older than retention_days into daily_stats, then deletes
        them. Runs once a day and never on the write path.
        """
        cutoff_day = (datetime.fromtimestamp(now) - timedelta(days=self.retention_days)).date()
        cutoff = time.mktime(cutoff_day.timetuple())

        try:
            with self._write_lock:
                writer = self._writer_connection()
                with writer:
                    writer.execute(_ROLLUP_SQL, (cutoff,))
                    writer.execute(_ROLLUP_CLOSEST_SQL)
                    cursor = writer.execute(
                        "DELETE FROM contacts WHERE last_seen < ?", (cutoff,)
                    )
                    pruned = cursor.rowcount
                # PRAGMA optimize after pruning keeps the query planner honest.
                # Deliberately no scheduled VACUUM — it rewrites the entire
                # database, which is exactly the bulk write we are avoiding.
                writer.execute("PRAGMA optimize")
            if pruned:
                self.logger.info(
                    f"Retention pruned {pruned} contact(s) older than "
                    f"{self.retention_days} days into daily_stats."
                )
            self._invalidate_counters()
        except Exception as e:
            self.logger.error(f"Retention pass failed: {e}")

    # --- Counters for the E-Ink display ---

    def _invalidate_counters(self) -> None:
        self._counter_cache = None

    def _counters(self) -> Dict[str, int]:
        cache = self._counter_cache
        if cache is not None and (time.time() - self._counter_cache_at) < COUNTER_CACHE_SECONDS:
            return cache

        try:
            connection = self._reader()
            midnight = _local_midnight()

            daily = connection.execute(
                "SELECT COUNT(DISTINCT hex) AS n FROM contacts WHERE first_seen >= ?",
                (midnight,),
            ).fetchone()["n"]

            # total_seen is the *sum of daily uniques*, matching the old
            # in-memory counter so the number on the E-Ink screen does not
            # visibly jump after this deploy. An aircraft seen on three days
            # counts three times — a daily commuter flight counts once per day.
            live = connection.execute(
                f"""
                SELECT COALESCE(SUM(n), 0) AS total FROM (
                    SELECT COUNT(DISTINCT hex) AS n
                    FROM contacts
                    GROUP BY {LOCAL_DAY % 'first_seen'}
                )
                """
            ).fetchone()["total"]

            # Days already rolled off into daily_stats no longer have contact
            # rows. The NOT IN guard keeps a partially-rolled day from being
            # counted twice.
            rolled = connection.execute(
                f"""
                SELECT COALESCE(SUM(unique_aircraft), 0) AS total
                FROM daily_stats
                WHERE day NOT IN (SELECT DISTINCT {LOCAL_DAY % 'first_seen'} FROM contacts)
                """
            ).fetchone()["total"]

            # The number most people *think* "total seen" means. Given its own
            # name rather than quietly redefining the existing one. Only spans
            # retained contacts — rolled-off days keep counts, not identities.
            distinct_ever = connection.execute(
                "SELECT COUNT(DISTINCT hex) AS n FROM contacts"
            ).fetchone()["n"]

            cache = {
                "daily_seen": int(daily),
                "total_seen": int(live) + int(rolled),
                "distinct_aircraft_ever": int(distinct_ever),
            }
        except Exception as e:
            self.logger.error(f"Failed to compute history counters: {e}")
            cache = self._counter_cache or {
                "daily_seen": 0,
                "total_seen": 0,
                "distinct_aircraft_ever": 0,
            }

        self._counter_cache = cache
        self._counter_cache_at = time.time()
        return cache

    @property
    def daily_seen(self) -> int:
        """Distinct aircraft whose visit started since local midnight."""
        return self._counters()["daily_seen"]

    @property
    def total_seen(self) -> int:
        """Sum of daily uniques across all days. Survives service restarts."""
        return self._counters()["total_seen"]

    @property
    def distinct_aircraft_ever(self) -> int:
        """Distinct hexes across every retained contact."""
        return self._counters()["distinct_aircraft_ever"]

    # --- Queries ---

    def GetContacts(
        self,
        before: Optional[float] = None,
        before_id: Optional[int] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Most recent contacts first, keyset-paginated.

        Keyset rather than OFFSET on purpose: rows are inserted underneath the
        cursor as aircraft come and go, and offset pagination silently skips
        and repeats rows under exactly those conditions. `id` breaks ties on
        identical last_seen values.
        """
        limit = max(1, min(int(limit), 500))

        clauses = []
        params: List[Any] = []
        if before is not None:
            if before_id is not None:
                clauses.append("(last_seen < ? OR (last_seen = ? AND id < ?))")
                params.extend([before, before, before_id])
            else:
                clauses.append("last_seen < ?")
                params.append(before)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        try:
            rows = self._reader().execute(
                f"""
                SELECT id, hex, flight, registration, aircraft_type, origin, destination,
                       first_seen, last_seen, closest_nm, closest_at, closest_bearing,
                       min_altitude, max_altitude, max_speed, sample_count, closed
                FROM contacts
                {where}
                ORDER BY last_seen DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        except Exception as e:
            self.logger.error(f"Contact query failed: {e}")
            return {"contacts": [], "next_before": None, "next_before_id": None}

        contacts = [dict(row) for row in rows]
        next_before = contacts[-1]["last_seen"] if len(contacts) == limit else None
        next_before_id = contacts[-1]["id"] if len(contacts) == limit else None
        return {
            "contacts": contacts,
            "next_before": next_before,
            "next_before_id": next_before_id,
        }

    def GetStats(self, range_key: str = "today") -> Dict[str, Any]:
        """
        Aggregates computed in SQL. Never make a client page through thousands
        of contacts to work out "closest approach today".
        """
        since = _range_start(range_key)
        where = "WHERE first_seen >= ?" if since is not None else ""
        params: Tuple = (since,) if since is not None else ()

        empty = {
            "range": range_key,
            "since": since,
            "contact_count": 0,
            "distinct_aircraft": 0,
            "closest_nm": None,
            "closest_hex": None,
            "closest_flight": None,
            "closest_at": None,
            "busiest_hour": None,
            "busiest_hour_count": 0,
        }

        try:
            connection = self._reader()

            totals = connection.execute(
                f"SELECT COUNT(*) AS contacts, COUNT(DISTINCT hex) AS aircraft FROM contacts {where}",
                params,
            ).fetchone()

            closest = connection.execute(
                f"""
                SELECT hex, flight, closest_nm, closest_at
                FROM contacts {where}
                ORDER BY closest_nm ASC
                LIMIT 1
                """,
                params,
            ).fetchone()

            busiest = connection.execute(
                f"""
                SELECT strftime('%H', first_seen, 'unixepoch', 'localtime') AS hour,
                       COUNT(*) AS n
                FROM contacts {where}
                GROUP BY hour
                ORDER BY n DESC, hour ASC
                LIMIT 1
                """,
                params,
            ).fetchone()
        except Exception as e:
            self.logger.error(f"Stats query failed: {e}")
            return empty

        return {
            "range": range_key,
            "since": since,
            "contact_count": totals["contacts"] if totals else 0,
            "distinct_aircraft": totals["aircraft"] if totals else 0,
            "closest_nm": closest["closest_nm"] if closest else None,
            "closest_hex": closest["hex"] if closest else None,
            "closest_flight": closest["flight"] if closest else None,
            "closest_at": closest["closest_at"] if closest else None,
            "busiest_hour": int(busiest["hour"]) if busiest and busiest["hour"] is not None else None,
            "busiest_hour_count": busiest["n"] if busiest else 0,
        }


# --- SQL and row helpers --------------------------------------------------

_COLUMNS = (
    "hex, flight, registration, aircraft_type, origin, destination, "
    "first_seen, last_seen, closest_nm, closest_at, closest_bearing, "
    "min_altitude, max_altitude, max_speed, sample_count, closed"
)

_INSERT_SQL = f"INSERT INTO contacts ({_COLUMNS}) VALUES ({', '.join(['?'] * 16)})"

_UPDATE_SQL = """
UPDATE contacts SET
    hex = ?, flight = ?, registration = ?, aircraft_type = ?, origin = ?,
    destination = ?, first_seen = ?, last_seen = ?, closest_nm = ?,
    closest_at = ?, closest_bearing = ?, min_altitude = ?, max_altitude = ?,
    max_speed = ?, sample_count = ?, closed = ?
WHERE id = ?
"""

# Rolls each expiring day's contacts into a single daily_stats row. Grouped by
# first_seen's local day, matching how daily_seen is defined, so a visit that
# straddles midnight is counted on the day it began.
#
# In practice a given day is rolled exactly once (its contacts are deleted in
# the same transaction), so the ON CONFLICT arm only fires if a day was
# partially rolled by an interrupted earlier pass. Summing is the right
# approximation there for a "sum of daily uniques" total.
_ROLLUP_SQL = f"""
INSERT INTO daily_stats (day, contact_count, unique_aircraft, closest_nm, closest_hex)
SELECT {LOCAL_DAY % 'first_seen'} AS day,
       COUNT(*),
       COUNT(DISTINCT hex),
       MIN(closest_nm),
       NULL
FROM contacts
WHERE last_seen < ?
GROUP BY day
ON CONFLICT(day) DO UPDATE SET
    contact_count   = daily_stats.contact_count + excluded.contact_count,
    unique_aircraft = daily_stats.unique_aircraft + excluded.unique_aircraft,
    closest_nm      = MIN(COALESCE(daily_stats.closest_nm, excluded.closest_nm),
                          COALESCE(excluded.closest_nm, daily_stats.closest_nm))
"""

# Fills in which aircraft made that day's closest approach. Must run before the
# DELETE, while the contact rows still exist.
_ROLLUP_CLOSEST_SQL = f"""
UPDATE daily_stats SET closest_hex = (
    SELECT c.hex FROM contacts AS c
    WHERE {LOCAL_DAY % 'c.first_seen'} = daily_stats.day
    ORDER BY c.closest_nm ASC LIMIT 1
)
WHERE closest_hex IS NULL
  AND EXISTS (
    SELECT 1 FROM contacts AS c
    WHERE {LOCAL_DAY % 'c.first_seen'} = daily_stats.day
  )
"""


def _nullable(value: str) -> Optional[str]:
    """Stores UNKNOWN identity as SQL NULL rather than a literal '???'."""
    return None if value == UNKNOWN or not value else value


def _contact_values(contact: Contact, closed: int) -> Tuple:
    return (
        contact.hex,
        _nullable(contact.flight),
        _nullable(contact.registration),
        _nullable(contact.aircraft_type),
        _nullable(contact.origin),
        _nullable(contact.destination),
        contact.first_seen,
        contact.last_seen,
        contact.closest_nm,
        contact.closest_at,
        contact.closest_bearing,
        contact.min_altitude,
        contact.max_altitude,
        contact.max_speed,
        contact.sample_count,
        closed,
    )


def _local_midnight(now: Optional[float] = None) -> float:
    reference = datetime.fromtimestamp(now) if now is not None else datetime.now()
    return time.mktime(reference.replace(hour=0, minute=0, second=0, microsecond=0).timetuple())


def _range_start(range_key: str) -> Optional[float]:
    if range_key == "today":
        return _local_midnight()
    if range_key == "week":
        return _local_midnight() - 6 * 24 * 60 * 60
    return None
