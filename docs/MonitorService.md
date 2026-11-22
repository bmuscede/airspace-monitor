# Monitor Service

## Overview

The monitor-service is the core orchestrator of the Airspace Monitor project. Running on a headless Raspberry Pi (DietPi), it handles live ADS-B data ingestion, external API routing, background database management, and physical hardware control (SPI for the E-Ink panel, USB serial for the split-flap).

## Tech Stack

* **Language:** Python 3
* **Web Framework:** FastAPI with Uvicorn
* **Hardware Libraries:** pyserial (USB serial for the Split-Flap), spidev (SPI for E-Ink), waveshare-epaper. The Waveshare driver reaches for `gpiozero`, which needs the `lgpio` pin factory; both are installed from apt (`python3-gpiozero`, `python3-lgpio`) and reached through a venv created with `--system-site-packages`.
* **Data Processing:** requests, csv
* **Persistence:** SQLite (WAL mode)

## Runtime state: a three-way split

Runtime state used to live in a single `SystemState` class that mixed three
unrelated concerns. It is now split three ways, with strictly separated
responsibilities:

| Component | Owns | Knows about |
|---|---|---|
| `controller/state.py` — `SystemState` | Hardware and service state only | Nothing else |
| `controller/tracker.py` — `ContactTracker` | Live air picture, track continuity, event emission | Nothing else — **no disk I/O whatsoever** |
| `data/history.py` — `HistoryStore` | SQLite persistence, flush policy, retention | Subscribes to tracker events |

The dependency arrow only points one way: `HistoryStore` subscribes to
`ContactTracker`, never the reverse. The tracker has no database handle, no
file path, and does not import `sqlite3`. That constraint is what guarantees a
per-cycle update costs zero writes to the SD card, and it is what makes the
tracker directly unit-testable with synthetic `Aircraft` lists and no mocking.

`Controller.GetState()` composes the API snapshot from `SystemState` and
`ContactTracker`. `SystemStateSnapshot` is unchanged on the wire.

### state.py (Hardware and service state)

Uptime, whether the loop is running, which display is active, whether readsb is
feeding us, and the last update timestamp. Nothing about aircraft. Guarded by an
`RLock`.

### tracker.py (The live air picture)

A **contact** is one aircraft's *visit* to our airspace: from first detection
until the receiver stops hearing it for longer than `history.contact_gap_seconds`
(default 300). Contacts persist across sweeps, so the system can finally tell
"new contact this sweep" apart from "overhead for ten minutes".

`update(aircraft_list)` runs once per hardware cycle, replacing the old
`SystemState.update_aircraft()`. It opens contacts for unseen hexes, merges
telemetry and identity into known ones, re-runs the display-target selection,
and sweeps for departures. The departure sweep runs **even when the sweep list
is empty**, or contacts would never close during quiet periods.

The tracker takes ownership of the `Aircraft` objects passed in, so a cycle
costs zero model copies. External reads (`all_aircraft`, `contacts`,
`get_contact`) return copies.

#### Best-known identity

Identity arrives late and inconsistently: `_read_aircraft` hardcodes `"???"`
(`models.UNKNOWN`) for type and registration, and FlightAware enrichment only
fires once per contact. The last sweep is routinely *less* identified than what
we knew mid-visit, so `flight`, `registration`, `aircraft_type`, `origin` and
`destination` are **sticky** — the tracker keeps the best non-unknown value it
has ever seen and never blindly overwrites with the latest sweep. Positional
telemetry (lat, lon, altitude, speed, heading, distance, bearing) always takes
the latest value.

A consequence worth exploiting: enrichment is now a per-*contact* event rather
than a per-sweep one. `Controller._on_tracker_event` calls FlightAware when a
contact opens with an unresolved route (retrying on the first update where a
callsign appears), and the answer sticks for the rest of the visit. This makes
the TTL cache in `flightaware.py` largely redundant; it is left in place but no
longer load-bearing.

#### The event contract

Three transitions, defined as dataclasses in `models.py`. **This is the
load-bearing interface for later phases** — Phase 3 streams these over SSE and
Phase 4 dead-reckons between them.

* **`ContactOpened(contact)`** — a hex not seen within the gap window.
* **`ContactUpdated(contact, previous)`** — telemetry refresh on a known track.
  `previous` is the `Aircraft` the contact carried before this sweep, so a
  subscriber can compute deltas without keeping its own shadow copy.
* **`ContactClosed(contact)`** — gap timeout exceeded, or a clean shutdown.
  Carries the completed record.

Subscribe with `tracker.subscribe(handler)`. Two rules matter:

1. **Handlers are never invoked while the tracker lock is held.** `HistoryStore`
   does SQLite I/O in its handler, and dispatching under the lock would block
   every API read for the duration of a disk write. The pattern is: mutate under
   lock → collect events into a local list → release lock → dispatch.
2. **A subscriber that raises cannot kill the hardware loop.** Every handler call
   is wrapped and failures are logged.

#### Display target selection

The sticky-closest logic that used to live in `Controller._pick_closest` is now
`ContactTracker.current_display_target`. It reasons about whether a contact
persists across cycles, which is tracker behaviour and had no business being an
orchestrator side effect. All four rules are preserved exactly:

1. Pick the closest when nothing is displayed.
2. Keep the current aircraft while it remains in range.
3. Switch only when another is *strictly* closer.
4. Fall back to the closest when the current one leaves range.

Two details that a rewrite would quietly break: "still in range" means present
in *this sweep*, not merely still an open contact; and rule 3 compares against
the target's distance as of the *previous* cycle. That one-cycle hysteresis is
what stops the E-Ink thrashing between two converging aircraft.

#### Known behaviour

If `readsb` dies, `_read_aircraft` returns `[]` and every contact will close
after the gap timeout, recording a mass departure that never happened. Accepted
for now — but the History UI will eventually want to tell "quiet sky" apart from
"receiver down", which needs a receiver-health signal rather than an empty sweep.

### history.py (Contact persistence)

SQLite at `data/history.db`, created on first run. `schema_version` is populated
so future phases have a migration hook.

#### Write policy: write on close, not on ping

**A contact is only worth writing once, when it closes.** While an aircraft is
in range everything we care about is still changing, so repeated writes would be
pure waste of the resource we are protecting.

* Live tracks stay in the tracker's memory. Zero I/O.
* On `ContactClosed`, write one row.

That is roughly one insert per aircraft per visit — a few hundred a day, against
the ~864,000 we would get logging every sweep at 2s intervals. Three orders of
magnitude, falling out of the design rather than needing a batching layer.

**Backstop flush:** every `history.flush_seconds` (default 300), currently-open
contacts are written in a single transaction with `closed = 0`. Losing a few
minutes of open contacts to a power cut is acceptable; losing hours is not.

#### The `closed` flag

A backstop flush writes `closed = 0`; contact closure updates the row to
`closed = 1`. **On startup, any surviving `closed = 0` rows are orphans from an
unclean shutdown** and are marked closed — they are as complete as they will
ever be. This turns a power cut from data loss into slightly-truncated records,
for free.

To update rather than duplicate a flushed row, `HistoryStore` keeps a private
`(hex, first_seen) → rowid` map. There is deliberately **no database id on the
`Contact` model** — that would leak persistence into the tracker and break the
separation.

#### Connections

* PRAGMAs on connect: `journal_mode=WAL`, `synchronous=NORMAL`,
  `busy_timeout=5000`. WAL is chosen primarily so API reads can proceed
  concurrently with hardware-thread writes, not for wear.
* Single writer, owned by the hardware thread, guarded by a lock.
* Readers get their own connection via `threading.local()`. One shared
  connection with `check_same_thread=False` would serialise API reads behind
  hardware writes.

#### Counters

`_push_to_display` reads `daily_seen` and `total_seen` on **every** hardware
cycle. These are cached in memory, refreshed at most every 60 seconds, and
invalidated on contact close — they must never become SQL queries on that path.

* `daily_seen` = distinct hexes whose visit started since local midnight.
* `total_seen` = **sum of daily uniques**, matching the previous in-memory
  behaviour so the number on the E-Ink screen does not visibly jump after this
  deploy. Note that this double-counts an aircraft seen on multiple days — a
  daily commuter flight counts once per day. Computed from the per-day distinct
  counts in `contacts`, plus `daily_stats.unique_aircraft` for days already
  rolled off by retention.
* `distinct_aircraft_ever` = distinct hexes across all retained contacts. This
  is the number most people *think* "total seen" means, so it gets its own name
  rather than quietly redefining the existing one. Exposed on
  `/api/history/stats` for the future History UI.

Because these now come from disk, **`total_seen` no longer resets to zero on
every service restart.** That was the live user-visible bug this phase fixes.

#### Retention

Once per day, contacts older than `history.retention_days` (default 90) are
rolled into `daily_stats` and deleted. Never on the write path. `PRAGMA optimize`
runs after pruning; there is deliberately **no scheduled `VACUUM`** — it rewrites
the entire database, which is exactly the kind of bulk write we are avoiding.

### controller.py (The Orchestrator)

The entry point of the application. It utilizes Python's threading module to solve the blocking issue of hardware loops:

* **Main Thread:** Runs `_hardware_loop()`, polling readsb JSON data, advancing
  the contact tracker, and pushing updates to the active physical display.
* **Daemon Thread:** Runs the FastAPI web server (uvicorn) on port 8000,
  listening for React dashboard requests.

#### Telemetry is normalised in the model, not the parsers

`Aircraft` declares `altitude`, `speed` and `heading` as `int`, and the feeds do
not agree. readsb sends `"gs": 208.9` and `"track": 164.17`, AeroAPI does the
same for groundspeed and heading, `alt_baro` is the literal string `"ground"`
for an aircraft on the deck, and any field the aircraft has not transmitted
arrives as `None`. Pydantic will not narrow a fractional float to `int`, so
each of these raises a validation error.

That mattered more than it sounds. The error surfaced inside `_hardware_loop()`,
which logs it and skips the cycle — so the display froze for exactly as long as
an aircraft was within range, and worked perfectly whenever the sky was empty.

`mode="before"` field validators on `Aircraft` round whatever arrives and fall
back to `0` for anything unreadable, so a bad field costs one value rather than
the whole sweep. `heading` additionally wraps modulo 360, because `359.7`
rounds to `360` — the same direction as `0`, but a character wider in a
three-column cell. `StateInformation.range` gets the same treatment: it comes
straight from `radar.max_range_nm`, and `/api/config` validates that a key
exists but not what type its value is.

This lives in the model rather than in `_read_aircraft` and `_read_aircraft_dev`
deliberately. It is the one point every `Aircraft` passes through — live readsb,
dev-mode FlightAware, and contacts rehydrated from the history database — so a
third feed cannot reintroduce the bug. `int` is kept as the contract rather
than widening the fields to `float`: the E-Ink panel renders them straight into
fixed-width columns with `f"{heading}"`, `Contact`'s envelope fields are ints,
and `history.py` stores `max_speed` as `INTEGER`.

#### Clean shutdown

`Shutdown()` is **idempotent and safe from any thread**. It sets the stop flag,
wakes the hardware loop out of its sleep, and — if called from another thread —
waits for the drain to finish.

The actual flush always happens on the hardware thread, in `_finalize()`: SQLite
connections are thread-affine, and a signal handler finalising inline could
re-enter the writer mid-statement. `_finalize()` closes all open contacts through
the tracker (emitting `ContactClosed` so `HistoryStore` persists them), then
closes the database.

Every shutdown route is wired in:

* `SIGTERM` and `SIGINT` handlers. `systemctl restart` sends SIGTERM, so this
  covers both the systemd path *and* the dashboard's Restart Services button.
* FastAPI's shutdown event, as a secondary hook.
* `POST /api/shutdown`, which blocks until the flush has actually happened.

The systemd unit sets `TimeoutStopSec=30`, comfortably above the 10s shutdown
timeout plus one hardware cycle. Dropping it below ~15s risks a SIGKILL
mid-flush, which shows up as `closed = 0` orphans on the next start.

### api.py (The Web Interface)

Defines the REST endpoints consumed by the React dashboard.

Some examples of the API are as follows:
* GET /api/flights: Returns active overhead flights.
* GET /api/state: Returns the composed system state snapshot.
* POST /api/mode: Toggles between 'E-Ink' and 'Split-Flap'.
* POST /api/git-pull: Executes an OS-level subprocess call to update the repo.
* POST /api/update-db: Uses FastAPI's BackgroundTasks to download the 50MB aircraft database without blocking the UI.
* GET /api/history/contacts: Recent completed contacts, most recent first.
* GET /api/history/stats: Aggregate history stats for a range.

`/api/flights` and `/api/state` are unchanged on the wire. The dashboard needs
no frontend changes for this phase.

#### History endpoints

**`GET /api/history/contacts?before=<last_seen>&before_id=<id>&limit=50`** —
most recent first, **keyset-paginated, not `OFFSET`-paginated**. Rows are
inserted underneath the cursor as aircraft come and go, and offset pagination
silently skips and repeats rows under exactly those conditions. Page forward
using the `next_before` / `next_before_id` values from the previous response.

**`GET /api/history/stats?range=today|week|all`** — contact count, distinct
aircraft, closest approach and which aircraft made it, and busiest hour. All
computed **in SQL**: never make a client page through thousands of contacts to
work out "closest approach today".

### aircraft_database.py (Local Caching)

Manages the OpenSky Network aircraft database. Loads the CSV of ADS-B hex codes in `data/aircraft_database.csv` and uses that to get aircraft types and tail numbers locally instead of hitting the FlightAware API for every flight.

### flightaware.py (External Routing)

Wraps the FlightAware AeroAPI.

Used exclusively to fetch Origin/Destination IATA codes (e.g., YOW -> LHR), as this data is not broadcasted via raw ADS-B.

Includes a Time-To-Live (TTL) memory cache. Since enrichment moved to
contact-open this is largely redundant, but it is kept as a cheap safety net for
repeated visits by the same flight number.

### logs.py (Two handlers, split by level and destination)

The database write policy is carefully frugal, so the logger has to be too — the
old configuration (50MB × 2 backups, with a per-cycle INFO line in dev mode and
an INFO line on every FlightAware cache hit) produced a write stream that
dwarfed the contact inserts.

1. **Live handler → tmpfs** (`/var/log/airspace-monitor/system.log`). Level INFO
   by default. This is what `/api/logs` tails to feed the dashboard Logs view.
   Being in RAM, writes are free.
2. **Persistent handler → SD** (`system.error.log` next to the service). Level
   **WARNING and above only**. This survives reboots and is what we actually
   need for diagnosing failures.

This delivers the "flush periodically" intent more cleanly than copying files on
a timer: the entries worth keeping are written immediately and are low-volume,
and the high-volume chatter never touches the card at all.

**Sizing is for RAM, not disk.** A Pi Zero 2 W has 512MB. The live handler is
5MB × 2 backups and the persistent one 2MB × 2 — the old 50MB × 2 on tmpfs would
have eaten nearly a third of available memory, and `/api/logs` only reads the
last 200 lines anyway. `os/setup.sh` mounts a dedicated 32MB tmpfs for the live
log rather than relying on DietPi's shared 20MB RAMlog.

The on-disk format is unchanged and must stay that way — `/api/logs` parses it
by splitting on spaces and the dashboard expects `timestamp`, `level`, `source`,
`message`.

Under systemd, stdout goes to the journal, which is another write stream on the
same card, so the console handler drops to WARNING when no TTY is attached.

`log_level` (default `INFO`) is configurable and applies to the live handler
only. The persistent handler stays pinned at WARNING regardless — that split is
the design, not a default.

### Hardware Drivers

1. eink_display.py: Handles SPI communication and Pillow (PIL) image generation for the E-Ink dashboard.

   Everything above `_writeToScreen` draws in reading order, so no layout code
   carries the case's orientation. `_orient_for_panel` is the single place that
   knows the panel is mounted upside down in it, and `eink.rotate_180` is what
   turns that off for a panel mounted the other way up. It is a `ROTATE_180`
   transpose rather than a resample, so the image is permuted, not softened,
   which matters on a seven-colour panel that cannot dither cleanly.

   The rotation applies to the hardware write path only. `DevDisplay` overrides
   `_writeToScreen` to draw into a Tk window, which is not in the case, so the
   desktop preview stays upright.

   **The panel must be woken before every write.** Waveshare's `sleep()` is not
   just a power state: it ends in `epdconfig.module_exit()`, which calls
   `SPI.close()` and drops the panel's power pin. Writing after that goes to a
   closed file descriptor and raises `[Errno 9] Bad file descriptor`, so
   `_writeToScreen` calls `init()` first — re-opening SPI and re-running the
   power-on sequence, which is what Waveshare's own examples do before each
   refresh — and sleeps the panel again in a `finally`, failed write included,
   so the next cycle starts from the state `init()` expects instead of leaking
   a descriptor per attempt. The constructor ends with a `sleep()` for the same
   reason: wake and sleep are always a pair. Left unpaired, the first update
   after start-up worked and every one after it failed.

   `_writeToScreen` returns whether the panel took the image, and
   `write_no_flight` / `write_flight_data` record their throttle state only on
   a `True`. That is load bearing: `_should_update_screen` refuses a repeat of
   the same state, so recording a failed write would suppress every retry until
   the aircraft changed, turning one bad write into a frozen panel. Panel
   errors are logged against the `EInk` logger rather than left to propagate,
   since the hardware loop reports anything that reaches it as a bare
   `Hardware loop error` and a display fault should not look like a fault in
   the radar sweep.

   Note that `_throttle_seconds` is 90 on the E-Ink driver, so a newly acquired
   flight can take up to a minute and a half to appear. That is deliberate — a
   full seven-colour refresh takes most of half a minute and the panel has a
   finite number of them in it.

2. splitflap_display.py: `SplitFlapDisplay`, the `Display` implementation for the mechanical
split-flap. It holds a `SplitFlapDriver` and decides what to put on it: the longest layout that
fits the configured flaps — logo flap and flight number, route, type — leaving altitude and speed
off, because they change every sweep and here every change is a row of flaps turning over. It
also owns the calibration state (see below).

The display itself is the `splitflap/` package, which knows nothing about aircraft:

| Module | What is in it |
|---|---|
| `splitflap/config.py` | `SplitFlapConfig`, `SplitFlapPosition`, `SplitFlapCharset`: the display as config.json describes it, and the flap tokens (`{ACA}857`) that name what is on a spool. Both the service and the calibration tool build theirs with `SplitFlapConfig.from_service_section()` |
| `splitflap/protocol.py` | The wire format Scott Bezek's Chainlink firmware speaks: COBS framing, a CRC32 trailer and the protobuf messages in `proto/splitflap.proto`, hand-rolled so the service needs no protobuf runtime. Frames in and out as bytes, and everything the firmware tells us: its enums, its messages, and the `SplitFlapStatus` / `SplitFlapModuleStatus` snapshots built out of them, with the questions worth asking of one (`idle`, `text`, `faults`, `healthy`). It knows nothing about serial ports |
| `splitflap/driver.py` | `SplitFlapDriver`: the connection. Thread-safe, queues writes and retries them until acknowledged, tracks every module's state, re-homes modules that fall into `SENSOR_ERROR` (rate limited, then gives up), and reconnects when the USB port drops |
| `splitflap/calibrate.py` | The command line tool for building and checking a display (see below) |

## Configuration

`config.json` is nested, and every key is addressed with dots:
`ConfigManager.Get("radar.home_lat")` reads one value, `Get("radar")` returns
the whole object, and `Set("radar.home_lat", 43.65)` writes one value without
disturbing its siblings. `POST /api/config` accepts either shape —
`{"radar": {"home_lat": 43.65}}` or `{"radar.home_lat": 43.65}` — applies only
the keys sent, and ignores (and reports) keys the config does not define.
Loading merges the file over the defaults object by object, so keys added to
`utils/config.py` later are always present.

That merge is what lets `os/setup.sh` seed a config at install time: it writes a
`config.json` holding nothing but `radar.home_lat` and `radar.home_lon`, taken
from `airspace-monitor.conf` on the boot partition, and every other key still
comes from the defaults. It only writes when there is no `config.json` already,
so re-running the installer never overwrites a configured appliance.

| Key | Default | Meaning |
|---|---|---|
| `radar.home_lat` / `radar.home_lon` | `0.0` | Where the receiver is. Every distance and bearing is computed from here, and the tracker shows whichever aircraft is closest, so an error here shows the wrong aircraft rather than merely misplacing it on the radar. `scripts/flash.sh` collects this and `os/setup.sh` seeds it on first boot; the defaults put the receiver in the Atlantic |
| `radar.max_range_nm` | 50 | Aircraft further away than this are dropped on read |
| `eink.rotate_180` | `true` | Turns the finished image 180 degrees on its way to the panel. On by default: the case in this repo holds the panel upside down. Set `false` for a panel mounted the other way up, or a bare one on the bench |
| `history.contact_gap_seconds` | 300 | How long a hex may go unheard before the visit is closed |
| `history.flush_seconds` | 300 | Backstop flush interval for open contacts |
| `history.retention_days` | 90 | Contacts older than this are rolled into `daily_stats` and deleted |
| `log_level` | `"INFO"` | Level for the live log; the persistent log stays at WARNING |
| `splitflap.enabled` | `false` | Whether the service talks to the split-flap display at all |
| `splitflap.port` | `""` | Serial port of the Chainlink controller; empty auto-detects it |
| `splitflap.rows` | `[]` | How the channels are grouped into rows of flaps, e.g. `[14, 14, 14]`; empty is one row |
| `splitflap.channels` | `[]` | One `{channel, charset}` per flap, left to right then top to bottom |
| `splitflap.charsets` | two | The flaps on each kind of spool, in the order they fall. Multi-character names are logo flaps (`{ACA}`) |
| `splitflap.auto_rehome` | on | Re-home modules that fall into `SENSOR_ERROR`, rate limited |
| `splitflap.calibration.calibrated` | `false` | Set once home offsets have been saved to the display's flash |

The Settings UI exposes the FlightAware and radar keys; the rest are edited in
the file. `log_level`, `history.contact_gap_seconds`, `history.flush_seconds`
and `history.retention_days` are applied to the live objects on save rather
than requiring a restart.

### Split-flap calibration

Home offsets live in the ESP32's flash, not in our config — what the config
remembers is whether they have ever been saved. On the first start where
`splitflap.calibration.calibrated` is false, the service homes every module,
checks none of them are faulted, asks the firmware to save the offsets, and
records that it did. A failed attempt leaves the flag alone, so the next start
tries again. Clearing the flag forces a fresh pass.

That automatic pass only persists the offsets the modules homed to. The
per-flap procedure that measures them (nudge a tenth of a flap at a time, name
the flap that is showing) needs someone watching the display, so it lives in
`monitor-service/splitflap/calibrate.py`, with a wrapper that stops the service
first — only one program can hold the serial port — and starts it again
afterwards:

```bash
./scripts/calibrate-splitflap.sh
```

The tool is also what to reach for when a display is being built or has gone
wrong. Every command takes `--config_dir` (default `.`) and an optional
`--port`, and anything after the script name is passed straight through:

| Command | What it is for |
|---|---|
| `calibrate [POS ...]` | Measure home offsets, then save them to the ESP32's flash (the default) |
| `status [--watch]` | Module states, home-sensor counters, loopback health, firmware build |
| `cycle [--delay N]` | Step every module through every flap: checks the charset matches the spool |
| `show "{ACA}857"` | Write text and report what wasn't on the flaps |
| `rehome [POS ...]` | Clear error counters and look for home again |
| `reset` | Hard-reset the ESP32 through the USB bridge |
| `ports` | List serial ports, marking the ones that look like an ESP32 |
| `forget` | Drop the saved calibration state, so the service calibrates on its next start |

A finished `calibrate` records `splitflap.calibration` in config.json itself,
so the service leaves the offsets alone from then on.

## Tests

```bash
pip install -r monitor-service/dev.requirements.txt
cd monitor-service && python -m pytest tests/ -q
```

`tests/test_tracker.py` covers the tracker with synthetic `Aircraft` lists and a
supplied clock. There is nothing to mock — **if a test in that file ever needs a
mock, the separation between tracker, state and history has gone wrong.**
`tests/test_history.py` exercises the store against a real SQLite file in a
`tmp_path`. `tests/test_aircraft_coercion.py` feeds readsb-shaped payloads --
fractional speeds and tracks, `"ground"`, absent fields -- through the real
`_read_aircraft`, built on a bare `Controller.__new__` so the parser can be
exercised without starting displays or the FlightAware client.
`tests/test_eink_display.py` drives the panel through a fake, so the rotation
and image handling are checked without hardware.
