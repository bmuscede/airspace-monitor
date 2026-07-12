import threading
import time
from datetime import datetime

class SystemState:
    """
    Thread-safe container for all runtime state.
    
    Shared between the hardware loop (daemon thread) and
    FastAPI's async workers. All mutations go through methods
    protected by a threading.Lock.
    """

    def __init__(self):
        self._lock = threading.Lock()

        self._start_time = datetime.now()
        self._system_running = False
        self._display_mode = "E-Ink"
        self._current_aircraft = None
        self._closest_aircraft = None
        self._all_aircraft = []
        self._last_update = 0.0
        self._readsb_connected = False

        self._count_day = datetime.now()
        self._total_aircraft_count = 0
        self._daily_unique_aircraft = set()

    # --- Getters ---

    @property
    def uptime(self):
        current_time = datetime.now()
        with self._lock:
            delta = current_time - self._start_time
            days = delta.days
            hours = delta.seconds // 3600

            return f"{days} d, {hours} hrs"

    @property
    def system_running(self):
        with self._lock:
            return self._system_running

    @property
    def display_mode(self):
        with self._lock:
            return self._display_mode

    @property
    def current_aircraft(self):
        with self._lock:
            # Return a copy to prevent mutations outside the lock.
            return dict(self._current_aircraft) if self._current_aircraft else None

    @property
    def closest_aircraft(self):
        with self._lock:
            return dict(self._closest_aircraft) if self._closest_aircraft else None

    @property
    def all_aircraft(self):
        with self._lock:
            return list(self._all_aircraft)

    @property
    def last_update(self):
        with self._lock:
            return self._last_update

    @property
    def readsb_connected(self):
        with self._lock:
            return self._readsb_connected

    @property
    def daily_aircraft_seen(self):
        with self._lock:
            if datetime.now().date() != self._count_day.date():
                return 0
            else:
                return len(self._daily_unique_aircraft)

    @property
    def total_aircraft_seen(self):
        with self._lock:
            return len(self._daily_unique_aircraft) + self._total_aircraft_count

    # --- Setters ---

    @system_running.setter
    def system_running(self, value: bool):
        with self._lock:
            self._system_running = value

    @display_mode.setter
    def display_mode(self, value: str):
        with self._lock:
            self._display_mode = value

    @current_aircraft.setter
    def current_aircraft(self, value):
        with self._lock:
            self._current_aircraft = dict(value) if value else None

    @closest_aircraft.setter
    def closest_aircraft(self, value):
        with self._lock:
            self._closest_aircraft = dict(value) if value else None

    @readsb_connected.setter
    def readsb_connected(self, value: bool):
        with self._lock:
            self._readsb_connected = value

    # --- Bulk Update (called by the hardware loop each cycle) ---

    def update_aircraft(self, all_aircraft: list, closest: dict = None):
        """
        Atomically updates the aircraft list, closest aircraft, and timestamp.
        Called once per hardware loop cycle.
        """
        with self._lock:
            self._all_aircraft = list(all_aircraft)
            self._closest_aircraft = dict(closest) if closest else None
            self._last_update = time.time()

            # Check if we need to purge the daily list.
            if datetime.now().date() != self._count_day.date():
                self._total_aircraft_count += len(self._daily_unique_aircraft)
                self._daily_unique_aircraft = set()
                self._count_day = datetime.now()
            for aircraft in all_aircraft:
                self._daily_unique_aircraft.add(aircraft.get("flight", "???"))
            
    # --- Toggle ---

    def toggle_display_mode(self) -> str:
        """Switches between E-Ink and Split-Flap. Returns the new mode."""
        with self._lock:
            if self._display_mode == "E-Ink":
                self._display_mode = "Split-Flap"
            else:
                self._display_mode = "E-Ink"
            return self._display_mode

    # --- Snapshot (for the API to return as JSON) ---

    def snapshot(self) -> dict:
        """Returns a complete, thread-safe copy of the current system state."""
        with self._lock:
            return {
                "systemRunning": self._system_running,
                "displayMode": self._display_mode,
                "currentAircraft": dict(self._current_aircraft) if self._current_aircraft else None,
                "closestAircraft": dict(self._closest_aircraft) if self._closest_aircraft else None,
                "aircraftCount": len(self._all_aircraft),
                "lastUpdate": self._last_update,
                "readsbConnected": self._readsb_connected,
            }
