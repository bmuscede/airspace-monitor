import json
import os
import signal
import threading
import uvicorn
from typing import List, Optional

from controller.state import SystemState
from controller.tracker import ContactTracker
from data.aircraft_database import AircraftDatabase
from data.flightaware import FlightAwareClient
from data.history import HistoryStore
from data.openweathermap import OpenweathermapClient
from display.dev_display import DevDisplay
from utils.config import ConfigManager
from utils.logs import GetLogger, SetLogLevel
from utils.utils import haversine, bearing
from models import (
    Aircraft,
    ContactClosed,
    ContactOpened,
    ContactUpdated,
    StateInformation,
    SystemStateSnapshot,
    UNKNOWN,
)


# Path to the readsb aircraft JSON feed.
AIRCRAFT_JSON_PATH = "/run/readsb/aircraft.json"

# Shared data directory (fonts, logos, aircraft database, contact history).
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

# Path to the local aircraft ICAO database CSV.
AIRCRAFT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aircraft_database.csv")

# Path to the contact history database.
HISTORY_DB_PATH = os.path.join(DATA_DIR, "history.db")

# Sleep intervals.
DEV_MODE_SLEEP=30
RPI_MODE_SLEEP=2

# How long a non-hardware thread will wait for the hardware loop to drain and
# flush before giving up on a clean shutdown.
SHUTDOWN_TIMEOUT_SECONDS = 10.0

class Controller:
    def __init__(self, configDir: str, devMode: bool = False):
        self.logger = GetLogger("Controller")
        self.devMode = devMode

        # Initialize the core libraries.
        self.configManager = ConfigManager(configDir)

        # Logging comes up before the config file is read, so apply the
        # configured level now that we have one.
        SetLogLevel(self.configManager.Get("log_level", "INFO"))

        self.state = SystemState()
        self.tracker = ContactTracker(
            contact_gap_seconds=self.configManager.Get("contact_gap_seconds", 300),
        )
        self.aircraftDB = AircraftDatabase(AIRCRAFT_DB_PATH)
        self.flightAwareClient = FlightAwareClient(
            apiKey=self.configManager.Get("flightaware_api_key", ""),
            apiURL=self.configManager.Get("flightaware_url", ""),
            cacheTTL=self.configManager.Get("cache_ttl", 3600),
        )
        self.weatherClient = OpenweathermapClient(
            api_key=self.configManager.Get("openweathermap_api_key", ""),
            api_url=self.configManager.Get("openweathermap_url", ""),
            weather_ttl=self.configManager.Get("weather_ttl", 3600),
        )

        # Persistence. Subscribes to the tracker rather than being called by
        # it — the tracker has no idea this exists.
        self.history = HistoryStore(
            db_path=HISTORY_DB_PATH,
            flush_seconds=self.configManager.Get("history_flush_seconds", 300),
            retention_days=self.configManager.Get("history_retention_days", 90),
            contacts_provider=lambda: self.tracker.contacts,
        )
        self.tracker.subscribe(self.history.handle_event)
        self.tracker.subscribe(self._on_tracker_event)

        # Hexes we have already attempted a FlightAware route lookup for during
        # the current visit. Enrichment is now a per-contact event rather than
        # a per-cycle one, which is what makes the TTL cache in flightaware.py
        # largely redundant.
        self._route_lookups_attempted = set()

        # Shutdown coordination. Shutdown() can arrive from a signal handler,
        # FastAPI's shutdown event, or /api/shutdown, so it has to be
        # idempotent and safe from any thread.
        self._shutdown_lock = threading.RLock()
        self._shutdown_requested = False
        self._finalized = False
        self._shutdown_complete = threading.Event()
        self._wake = threading.Event()
        self._hardware_thread = None

        # Display drivers.
        # Use DevDisplay when running without hardware.
        # This allows us to run on non-Raspberry Pi hardware.
        if self.devMode:
            self.logger.info("Running in development mode...")
            self._devDisplay = DevDisplay(mode="E-Ink")
            self.eink = self._devDisplay
            self.splitflap = self._devDisplay
        else:
            from display.eink_display import EInkDisplay
            from display.splitflap_display import SplitFlapDisplay
            self._devDisplay = None
            self.eink = EInkDisplay()
            self.splitflap = SplitFlapDisplay()

    def Start(self) -> None:
        """
        Starts the FastAPI web server and the hardware monitoring thread.

        The web server runs in a daemon thread so that when the main
        thread (hardware loop) exits, the process shuts down cleanly.
        """
        self.logger.info("Starting Airspace Monitor controller...")

        # Wire up the API module with a reference to this controller.
        import controller.api
        controller.api.controller = self

        self._install_signal_handlers()

        # Start the FastAPI server in a background daemon thread.
        web_thread = threading.Thread(target=self._start_webserver, daemon=True)
        web_thread.start()

        # Run the hardware loop on the main thread.
        # This blocks forever until systemRunning is set to False.
        self._hardware_loop()

    def _install_signal_handlers(self) -> None:
        """
        Routes SIGTERM and SIGINT into the same clean shutdown path.

        systemctl restart sends SIGTERM, so this covers both the systemd path
        and our own /api/restart-service button. The handler only asks for
        shutdown — the hardware loop does the actual flush on its own thread,
        which keeps us out of SQLite reentrancy.
        """
        def handler(signum, _frame):
            self.logger.info(f"Received signal {signum}. Shutting down...")
            self.Shutdown()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError, AttributeError) as e:
                # Not the main thread, or the platform lacks the signal.
                self.logger.warning(f"Could not install handler for signal {sig}: {e}")

    def _start_webserver(self) -> None:
        """Runs the FastAPI/Uvicorn server on port 8000."""
        self.logger.info("Starting web server on 0.0.0.0:8000...")
        import controller.api
        uvicorn.run(controller.api.app, host="0.0.0.0", port=8000, log_level="warning")

    def _hardware_loop(self) -> None:
        """
        Continuously polls dump1090 for aircraft data, enriches it,
        advances the contact tracker, and pushes to the active display.
        """
        self.logger.info("Hardware loop started.")
        self._hardware_thread = threading.current_thread()
        self.state.system_running = True

        while self.state.system_running:
            try:
                # Read the list of aircraft detected in the current area.
                aircraft_list = self._read_aircraft() if not self.devMode else self._read_aircraft_dev()

                # Use the local DB to get other aircraft information.
                for ac in aircraft_list:
                    if ac.type == UNKNOWN:
                        info = self.aircraftDB.GetAircraftInfo(ac.hex)
                        ac.type = info.get("type", UNKNOWN)
                        ac.reg = info.get("reg", UNKNOWN)

                # Advance the air picture. This opens and closes contacts and
                # dispatches events to HistoryStore and _on_tracker_event,
                # which is where route enrichment is triggered.
                self.tracker.update(aircraft_list)
                self.state.last_update = self.tracker.last_update

                # Housekeeping: backstop flush and the daily retention pass.
                # Two timestamp comparisons unless something is actually due.
                self.history.Tick()

                # Push to the active display.
                self._push_to_display(self.tracker.current_display_target)

                # Figure out our sleep time.
                # Sleep for longer in dev mode versus regular hardware run.
                sleepTime = DEV_MODE_SLEEP if self.devMode else RPI_MODE_SLEEP

                # Event.wait rather than time.sleep so a shutdown request does
                # not have to sit through a full dev-mode cycle.
                if self._wake.wait(sleepTime):
                    self._wake.clear()

            except Exception as e:
                self.logger.error(f"Hardware loop error: {e}")
                if self._wake.wait(5):
                    self._wake.clear()

        self.logger.info("Hardware loop stopped.")

        # The loop owns the database connection, so it also owns the final
        # flush. Every other shutdown route just asks and waits.
        self._finalize()

    def _on_tracker_event(self, event) -> None:
        """
        Triggers FlightAware route enrichment once per contact.

        Route lookups used to run every cycle for whichever aircraft was on the
        display. Now that contacts persist across sweeps and identity is sticky,
        one lookup per visit is enough: the resolved origin/destination is
        merged into the contact and survives every subsequent sweep that comes
        back as UNKNOWN.

        A contact frequently opens before its callsign resolves, so we also
        retry on the first update where a flight number appears.
        """
        if isinstance(event, ContactClosed):
            self._route_lookups_attempted.discard(event.contact.hex)
            return

        if not isinstance(event, (ContactOpened, ContactUpdated)):
            return

        contact = event.contact
        if contact.hex in self._route_lookups_attempted:
            return
        if contact.flight == UNKNOWN:
            return
        if contact.origin != UNKNOWN and contact.destination != UNKNOWN:
            return

        self._route_lookups_attempted.add(contact.hex)
        try:
            origin, destination = self.flightAwareClient.GetRoute(contact.flight)
        except Exception as e:
            self.logger.error(f"Route lookup failed for {contact.flight}: {e}")
            return

        self.tracker.apply_identity(contact.hex, origin=origin, destination=destination)

    def _read_aircraft(self) -> List[Aircraft]:
        """
        Reads /run/readsb/aircraft.json, parses it, calculates
        distance/bearing from home, and filters to aircraft within range.

        Returns a normalised list of aircraft dicts.
        """
        try:
            with open(AIRCRAFT_JSON_PATH, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.state.readsb_connected = False
            return []
        except Exception as e:
            self.logger.error(f"Error reading aircraft.json: {e}")
            self.state.readsb_connected = False
            return []

        self.state.readsb_connected = True

        home_lat = self.configManager.Get("home_lat", 0.0)
        home_lon = self.configManager.Get("home_lon", 0.0)
        max_range = self.configManager.Get("max_radar_range_nm", 50)

        aircraft_list = []
        for ac in data.get("aircraft", []):
            lat = ac.get("lat")
            lon = ac.get("lon")

            # Skip aircraft without position data — we can't calculate distance.
            if lat is None or lon is None:
                continue

            dist = haversine(home_lat, home_lon, lat, lon)
            bear = bearing(home_lat, home_lon, lat, lon)

            # Filter to aircraft within our configured radar range.
            if dist > max_range:
                continue

            # Normalise the raw dump1090 fields into our standard shape.
            flight_raw = ac.get("flight", "").strip()
            aircraft_list.append(Aircraft(
                hex=ac.get("hex", "").strip().lower(),
                flight=flight_raw if flight_raw else UNKNOWN,
                altitude=ac.get("alt_baro", 0) or 0,
                speed=ac.get("gs", 0) or 0,
                heading=ac.get("track", 0) or 0,
                lat=lat,
                lon=lon,
                distance=round(dist, 1),
                bearing=bear,
                origin=UNKNOWN,
                destination=UNKNOWN,
                type=UNKNOWN,
                reg=UNKNOWN,
            ))

        # Sort by distance so closest is first.
        aircraft_list.sort(key=lambda x: x.distance)
        return aircraft_list

    def _read_aircraft_dev(self) -> List[Aircraft]:
        """
        Development mode simulation.
        Queries FlightAware API for nearby flights instead of
        relying on local radio hardware.

        Returns a normalised list of aircraft dicts.
        """
        home_lat = self.configManager.Get("home_lat", 0.0)
        home_lon = self.configManager.Get("home_lon", 0.0)
        max_range = self.configManager.Get("max_radar_range_nm", 50)

        # DEBUG, not INFO: this fired on every single cycle and was the single
        # largest contributor to the log write stream in dev mode.
        self.logger.debug(f"Simulating radar sweep via FlightAware ({max_range} NM)...")
        raw_flights = self.flightAwareClient.GetNearbyFlights(home_lat, home_lon, max_range)

        aircraft_list = []
        for ac in raw_flights:
            # FlightAware search API returns positional data inside 'last_position' or root depending on the endpoint
            pos = ac.get("last_position", {})
            lat = pos.get("latitude") if pos else ac.get("latitude")
            lon = pos.get("longitude") if pos else ac.get("longitude")

            if lat is None or lon is None:
                continue

            dist = haversine(home_lat, home_lon, lat, lon)
            bear = bearing(home_lat, home_lon, lat, lon)

            if dist > max_range:
                continue

            ident = ac.get("ident", "").strip()
            if not ident:
                ident = ac.get("registration", "").strip()

            # AeroAPI altitude is often returned in 100s of feet (FL)
            alt_raw = pos.get("altitude") if pos else ac.get("altitude")
            alt = (alt_raw * 100) if alt_raw else 0

            spd_raw = pos.get("groundspeed") if pos else ac.get("groundspeed")
            hdg_raw = pos.get("heading") if pos else ac.get("heading")

            aircraft_list.append(Aircraft(
                hex=ac.get("hexid", "").strip().lower(),
                flight=ident if ident else UNKNOWN,
                altitude=alt,
                speed=spd_raw or 0,
                heading=hdg_raw or 0,
                lat=lat,
                lon=lon,
                distance=round(dist, 1),
                bearing=bear,
                origin=UNKNOWN,
                destination=UNKNOWN,
                type=ac.get("aircraft_type", UNKNOWN),
                reg=ac.get("registration", UNKNOWN),
            ))

        aircraft_list.sort(key=lambda x: x.distance)
        self.state.readsb_connected = True
        return aircraft_list

    def _push_to_display(self, aircraft: Optional[Aircraft]) -> None:
        """
        Sends the current aircraft to the active display driver.
        """
        mode = self.state.display_mode
        driver = self.eink if mode == "E-Ink" else self.splitflap

        if aircraft is None:
            # Fetch the weather information.
            home_lat = self.configManager.Get("home_lat", 0.0)
            home_lon = self.configManager.Get("home_lon", 0.0)
            forecast = self.weatherClient.get_forecast(home_lat, home_lon)

            # Pass bundle information to write no flight.
            # daily_seen/total_seen come from HistoryStore's cached counters,
            # never a live SQL query — this runs on every hardware cycle.
            state_info = StateInformation(
                readsb_connected=self.state.readsb_connected,
                range=self.configManager.Get("max_radar_range_nm", 50),
                uptime=self.state.uptime,
                daily_seen=self.history.daily_seen,
                total_seen=self.history.total_seen
            )
            driver.write_no_flight(state_info, forecast)
            return

        driver.write_flight_data(aircraft)

    def GetAircraft(self) -> List[Aircraft]:
        """Returns all aircraft currently tracked (for the dashboard)."""
        return self.tracker.all_aircraft

    def GetState(self) -> dict:
        """
        Returns a snapshot of the full system state.

        Composed here rather than in SystemState: the system half and the
        aircraft half now live in two different objects, and this is the only
        place that knows about both. The wire shape is unchanged.
        """
        system = self.state.snapshot()
        snapshot = SystemStateSnapshot(
            systemRunning=system["systemRunning"],
            displayMode=system["displayMode"],
            currentAircraft=self.tracker.current_display_target,
            closestAircraft=self.tracker.closest_aircraft,
            aircraftCount=self.tracker.aircraft_count,
            lastUpdate=system["lastUpdate"],
            readsbConnected=system["readsbConnected"],
        )
        return snapshot.model_dump()

    def GetHistoryContacts(self, before=None, before_id=None, limit: int = 50) -> dict:
        """Recent completed contacts, newest first, keyset-paginated."""
        return self.history.GetContacts(before=before, before_id=before_id, limit=limit)

    def GetHistoryStats(self, range_key: str = "today") -> dict:
        """Aggregate history stats for a time range, computed in SQL."""
        stats = self.history.GetStats(range_key)
        stats["distinct_aircraft_ever"] = self.history.distinct_aircraft_ever
        return stats

    def ToggleDisplayMode(self) -> str:
        """Switches between E-Ink and Split-Flap. Returns the new mode."""
        new_mode = self.state.toggle_display_mode()
        self.logger.info(f"Display mode switched to {new_mode}.")

        # If running in no-display mode, tell the dev display which display to act as.
        if self._devDisplay is not None:
            self._devDisplay.set_mode(new_mode)

        return new_mode

    def Shutdown(self, timeout: float = SHUTDOWN_TIMEOUT_SECONDS) -> None:
        """
        Gracefully shuts down the hardware loop and flushes open contacts.

        Idempotent, and safe to call from any thread. The actual flush always
        happens on the hardware thread — SQLite connections are thread-affine,
        and a signal handler finalising inline could re-enter the writer
        mid-statement. Callers from other threads wait for the drain instead.
        """
        with self._shutdown_lock:
            already_requested = self._shutdown_requested
            self._shutdown_requested = True

        if not already_requested:
            self.logger.info("Shutdown requested.")

        self.state.system_running = False
        self._wake.set()

        # The hardware loop finalises itself on the way out.
        if self._hardware_thread is None or threading.current_thread() is self._hardware_thread:
            return

        if not self._shutdown_complete.wait(timeout):
            self.logger.warning(
                f"Hardware loop did not finish flushing within {timeout}s."
            )

    def _finalize(self) -> None:
        """
        Closes open contacts and the database. Runs exactly once, on the
        hardware thread.
        """
        with self._shutdown_lock:
            if self._finalized:
                return
            self._finalized = True

        try:
            # Emits ContactClosed for every open contact, which is what gets
            # them persisted with closed = 1 rather than lost.
            closed = self.tracker.close_all()
            if closed:
                self.logger.info(f"Flushed {len(closed)} open contact(s) on shutdown.")
        except Exception as e:
            self.logger.error(f"Error closing contacts on shutdown: {e}")

        try:
            self.history.Close()
        except Exception as e:
            self.logger.error(f"Error closing history store: {e}")

        self._shutdown_complete.set()
        self.logger.info("Shutdown complete.")
