import threading
from datetime import datetime

class SystemState:
    """
    Thread-safe container for hardware and service state.

    This is deliberately narrow: uptime, whether the loop is running, which
    display is active, and whether readsb is feeding us. The live air picture
    lives in ContactTracker and historical aggregates live in HistoryStore.
    SystemState knows about neither.

    Shared between the hardware loop (main thread) and FastAPI's async workers.
    All mutations go through methods protected by a threading.RLock.
    """

    def __init__(self):
        # RLock rather than Lock: nothing re-enters today, but every method
        # here takes the lock and it is one careless property call away from
        # deadlocking the hardware thread permanently.
        self._lock = threading.RLock()

        self._start_time = datetime.now()
        self._system_running = False
        self._display_mode = "E-Ink"
        self._last_update = 0.0
        self._readsb_connected = False

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
    def last_update(self):
        with self._lock:
            return self._last_update

    @property
    def readsb_connected(self):
        with self._lock:
            return self._readsb_connected

    # --- Setters ---

    @system_running.setter
    def system_running(self, value: bool):
        with self._lock:
            self._system_running = value

    @display_mode.setter
    def display_mode(self, value: str):
        with self._lock:
            self._display_mode = value

    @last_update.setter
    def last_update(self, value: float):
        with self._lock:
            self._last_update = value

    @readsb_connected.setter
    def readsb_connected(self, value: bool):
        with self._lock:
            self._readsb_connected = value

    # --- Toggle ---

    def toggle_display_mode(self) -> str:
        """Switches between E-Ink and Split-Flap. Returns the new mode."""
        with self._lock:
            if self._display_mode == "E-Ink":
                self._display_mode = "Split-Flap"
            else:
                self._display_mode = "E-Ink"
            return self._display_mode

    # --- Snapshot ---

    def snapshot(self) -> dict:
        """
        Returns the system-state half of the API snapshot.

        This is no longer a complete SystemStateSnapshot — the aircraft fields
        come from ContactTracker. Controller.GetState() composes the two.
        """
        with self._lock:
            return {
                "systemRunning": self._system_running,
                "displayMode": self._display_mode,
                "lastUpdate": self._last_update,
                "readsbConnected": self._readsb_connected,
            }
