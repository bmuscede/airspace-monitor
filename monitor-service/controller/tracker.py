import threading
import time
from typing import Callable, Dict, List, Optional

from models import (
    Aircraft,
    Contact,
    ContactClosed,
    ContactOpened,
    ContactUpdated,
    TrackerEvent,
    UNKNOWN,
)
from utils.logs import GetLogger

# How long a hex may go unheard before we call the visit over.
DEFAULT_CONTACT_GAP_SECONDS = 300


def _merge_identity(existing: str, incoming: str) -> str:
    """
    Keeps the best identity value we have ever seen for a field.

    Identity arrives late and inconsistently, so a later sweep is frequently
    *less* identified than an earlier one — _read_aircraft hardcodes UNKNOWN
    for type/reg, and FlightAware enrichment only ever runs once per contact.
    Blindly taking the latest value would throw away what we already knew.
    """
    if incoming and incoming.strip() and incoming.strip() != UNKNOWN:
        return incoming.strip()
    return existing


class ContactTracker:
    """
    The live air picture: which aircraft are up there right now, how long each
    has been up there, and which one the display should be showing.

    This class performs **no disk I/O of any kind**. It holds no database
    handle, no file path, and does not import sqlite3. That constraint is what
    guarantees a per-cycle update costs zero writes to the SD card, and it is
    what makes the whole thing directly unit-testable with synthetic Aircraft
    lists and no mocking.

    Persistence is HistoryStore's job. It subscribes to the events emitted here
    and never the other way round.

    Threading: mutated by the hardware loop, read by FastAPI's async workers.
    All state is guarded by an RLock. Event handlers are deliberately invoked
    *after* the lock is released — see update().
    """

    def __init__(
        self,
        contact_gap_seconds: int = DEFAULT_CONTACT_GAP_SECONDS,
        logger=None,
    ):
        # RLock, not Lock. Nothing re-enters today, but this class is about to
        # grow two more phases of callers and a self-deadlock here would hang
        # the hardware thread permanently.
        self._lock = threading.RLock()

        self.contact_gap_seconds = contact_gap_seconds
        self.logger = logger if logger is not None else GetLogger("ContactTracker")

        self._contacts: Dict[str, Contact] = {}
        self._handlers: List[Callable[[TrackerEvent], None]] = []
        self._last_update = 0.0

        # Sticky-closest display selection state. We keep the target's distance
        # as of the *previous* cycle because the switch rule compares this
        # sweep's closest against the target as we last knew it.
        self._display_target_hex: Optional[str] = None
        self._display_target_distance: Optional[float] = None
        self._closest_hex: Optional[str] = None

    # --- Subscription ---

    def subscribe(self, handler: Callable[[TrackerEvent], None]) -> None:
        """
        Registers a synchronous event handler.

        Handlers are called on the hardware thread with the tracker lock
        released. They receive the tracker's live Contact object and must treat
        it as read-only. A handler that raises is logged and skipped — a
        subscriber must never be able to kill the hardware loop.
        """
        with self._lock:
            self._handlers.append(handler)

    # --- Reads (external callers get copies) ---

    @property
    def contacts(self) -> List[Contact]:
        """All open contacts, as copies safe to use outside the lock."""
        with self._lock:
            return [c.model_copy(deep=True) for c in self._contacts.values()]

    @property
    def all_aircraft(self) -> List[Aircraft]:
        """
        Every tracked aircraft, nearest first, with sticky identity applied.

        One copy per aircraft per read (to_aircraft copies). The old
        SystemState copied on write *and* on read; internal paths below work on
        the live contacts directly and never pay the copy at all.
        """
        with self._lock:
            aircraft = [c.to_aircraft() for c in self._contacts.values()]
        aircraft.sort(key=lambda ac: ac.distance)
        return aircraft

    @property
    def aircraft_count(self) -> int:
        with self._lock:
            return len(self._contacts)

    @property
    def last_update(self) -> float:
        with self._lock:
            return self._last_update

    @property
    def current_display_target(self) -> Optional[Aircraft]:
        """
        The aircraft the physical display should be showing.

        This is the sticky-closest selection that used to live in
        Controller._pick_closest — it is tracker behaviour (it reasons about
        whether a contact persists across cycles) and had no business being an
        orchestrator side effect.
        """
        with self._lock:
            contact = self._contacts.get(self._display_target_hex) if self._display_target_hex else None
            return contact.to_aircraft() if contact else None

    @property
    def closest_aircraft(self) -> Optional[Aircraft]:
        with self._lock:
            contact = self._contacts.get(self._closest_hex) if self._closest_hex else None
            return contact.to_aircraft() if contact else None

    def get_contact(self, hex_code: str) -> Optional[Contact]:
        """Returns a copy of a single open contact, or None."""
        with self._lock:
            contact = self._contacts.get(hex_code)
            return contact.model_copy(deep=True) if contact else None

    # --- Identity injection (used by late enrichment) ---

    def apply_identity(self, hex_code: str, **fields: str) -> bool:
        """
        Folds externally resolved identity into an open contact.

        Used by the controller after a FlightAware lookup. Accepts any of
        flight / registration / aircraft_type / origin / destination and merges
        them with the same stickiness rule as a sweep, so a lookup that comes
        back UNKNOWN cannot erase what we already had.

        Returns True if the contact was still open.
        """
        allowed = ("flight", "registration", "aircraft_type", "origin", "destination")
        with self._lock:
            contact = self._contacts.get(hex_code)
            if contact is None:
                return False
            for name in allowed:
                if name in fields:
                    setattr(contact, name, _merge_identity(getattr(contact, name), fields[name]))
            return True

    # --- The per-cycle update ---

    def update(self, aircraft_list: List[Aircraft], now: Optional[float] = None) -> List[TrackerEvent]:
        """
        Advances the air picture by one radar sweep. Called once per hardware
        cycle, replacing the old SystemState.update_aircraft().

        Opens contacts for unseen hexes, merges telemetry and identity into
        known ones, re-runs the display-target selection, then sweeps for
        departures. Returns the events it dispatched.

        The tracker takes ownership of the Aircraft objects passed in; callers
        must not mutate them afterwards. This is what lets a cycle cost zero
        model copies.

        NOTE: if readsb dies, Controller._read_aircraft returns [] and every
        open contact will close once the gap timeout elapses — recording a mass
        departure that never happened. Accepted for now, but the History UI
        will eventually want to tell "quiet sky" apart from "receiver down",
        which needs a receiver-health signal rather than an empty sweep.
        """
        now = time.time() if now is None else now
        events: List[TrackerEvent] = []
        logs: List[str] = []

        with self._lock:
            # Work on a distance-sorted copy of the list. _read_aircraft
            # already sorts, but the display-target rules depend on it and
            # tests should not have to know that.
            sweep = sorted(aircraft_list, key=lambda ac: ac.distance)

            for aircraft in sweep:
                contact = self._contacts.get(aircraft.hex)
                if contact is None:
                    events.append(ContactOpened(self._open_contact(aircraft, now)))
                else:
                    previous = contact.aircraft
                    self._merge_sweep(contact, aircraft, now)
                    events.append(ContactUpdated(contact, previous))

            self._select_display_target(sweep, logs)

            # The departure sweep must run even on an empty list, or contacts
            # would never close during quiet periods.
            for contact in self._sweep_departures(now):
                events.append(ContactClosed(contact))
                logs.append(
                    f"Contact closed: {contact.flight} ({contact.hex}) after "
                    f"{contact.last_seen - contact.first_seen:.0f}s, "
                    f"closest {contact.closest_nm} nm."
                )

            self._last_update = now

        # Lock released. Log and dispatch out here: HistoryStore does SQLite
        # I/O in its handler, and dispatching under the lock would block every
        # API read for the duration of a disk write.
        for message in logs:
            self.logger.info(message)
        self._dispatch(events)
        return events

    def close_all(self, now: Optional[float] = None) -> List[TrackerEvent]:
        """
        Closes every open contact and dispatches ContactClosed for each.

        Called on clean shutdown so HistoryStore gets a chance to persist
        in-flight visits rather than losing them.
        """
        now = time.time() if now is None else now
        with self._lock:
            closing = list(self._contacts.values())
            self._contacts = {}
            self._display_target_hex = None
            self._display_target_distance = None
            self._closest_hex = None

        events: List[TrackerEvent] = [ContactClosed(c) for c in closing]
        if events:
            self.logger.info(f"Closing {len(events)} open contact(s).")
        self._dispatch(events)
        return events

    # --- Private helpers (all called with the lock held) ---

    def _open_contact(self, aircraft: Aircraft, now: float) -> Contact:
        contact = Contact(
            hex=aircraft.hex,
            first_seen=now,
            last_seen=now,
            aircraft=aircraft,
            closest_nm=aircraft.distance,
            closest_at=now,
            closest_bearing=aircraft.bearing,
            min_altitude=aircraft.altitude if aircraft.altitude > 0 else None,
            max_altitude=aircraft.altitude if aircraft.altitude > 0 else None,
            max_speed=aircraft.speed if aircraft.speed > 0 else None,
            sample_count=1,
            flight=_merge_identity(UNKNOWN, aircraft.flight),
            registration=_merge_identity(UNKNOWN, aircraft.reg),
            aircraft_type=_merge_identity(UNKNOWN, aircraft.type),
            origin=_merge_identity(UNKNOWN, aircraft.origin),
            destination=_merge_identity(UNKNOWN, aircraft.destination),
        )
        self._contacts[aircraft.hex] = contact
        return contact

    def _merge_sweep(self, contact: Contact, aircraft: Aircraft, now: float) -> None:
        # Positional telemetry always takes the latest value; only identity is
        # sticky.
        contact.aircraft = aircraft
        contact.last_seen = now
        contact.sample_count += 1

        if aircraft.distance < contact.closest_nm:
            contact.closest_nm = aircraft.distance
            contact.closest_at = now
            contact.closest_bearing = aircraft.bearing

        # A zero altitude/speed from readsb means "not reported", not "on the
        # ground at a standstill" — folding it into the envelope would make
        # min_altitude useless.
        if aircraft.altitude > 0:
            if contact.min_altitude is None or aircraft.altitude < contact.min_altitude:
                contact.min_altitude = aircraft.altitude
            if contact.max_altitude is None or aircraft.altitude > contact.max_altitude:
                contact.max_altitude = aircraft.altitude
        if aircraft.speed > 0:
            if contact.max_speed is None or aircraft.speed > contact.max_speed:
                contact.max_speed = aircraft.speed

        contact.flight = _merge_identity(contact.flight, aircraft.flight)
        contact.registration = _merge_identity(contact.registration, aircraft.reg)
        contact.aircraft_type = _merge_identity(contact.aircraft_type, aircraft.type)
        contact.origin = _merge_identity(contact.origin, aircraft.origin)
        contact.destination = _merge_identity(contact.destination, aircraft.destination)

    def _sweep_departures(self, now: float) -> List[Contact]:
        cutoff = now - self.contact_gap_seconds
        departed = [c for c in self._contacts.values() if c.last_seen < cutoff]
        for contact in departed:
            del self._contacts[contact.hex]
            if self._display_target_hex == contact.hex:
                self._display_target_hex = None
                self._display_target_distance = None
            if self._closest_hex == contact.hex:
                self._closest_hex = None
        return departed

    def _select_display_target(self, sweep: List[Aircraft], logs: List[str]) -> None:
        """
        Sticky-closest selection, moved verbatim from Controller._pick_closest.

        1. If nothing is currently displayed, pick the closest.
        2. If the currently displayed aircraft is still in range, keep it.
        3. Only switch when a new aircraft becomes *strictly* closer.
        4. If the displayed aircraft leaves range, fall back to the closest.

        "Still in range" means present in *this sweep*, not merely still an
        open contact — a contact lingers for the whole gap window, and using
        that here would freeze the display on an aircraft that has gone.

        The comparison in rule 3 deliberately uses the target's distance as of
        the previous cycle, which is what the original did (it read
        state.current_aircraft before update_aircraft overwrote it). Comparing
        against this sweep's distance instead would change which aircraft wins
        and the E-Ink would start thrashing.
        """
        if not sweep:
            self._display_target_hex = None
            self._display_target_distance = None
            self._closest_hex = None
            return

        closest = sweep[0]
        self._closest_hex = closest.hex

        current_hex = self._display_target_hex
        current_distance = self._display_target_distance

        if current_hex is None:
            self._display_target_hex = closest.hex
            self._display_target_distance = closest.distance
            logs.append(f"Displaying new aircraft: {self._label(closest)}")
            return

        still_in_range = any(ac.hex == current_hex for ac in sweep)

        if not still_in_range:
            previous_label = self._label_for_hex(current_hex)
            self._display_target_hex = closest.hex
            self._display_target_distance = closest.distance
            logs.append(
                f"Aircraft {previous_label} left range. "
                f"Switching to {self._label(closest)}."
            )
            return

        if closest.hex != current_hex and closest.distance < current_distance:
            logs.append(
                f"New closer aircraft detected: {self._label(closest)} "
                f"({closest.distance} nm vs {current_distance} nm)."
            )
            self._display_target_hex = closest.hex
            self._display_target_distance = closest.distance
            return

        # Keep the current aircraft; refresh the distance we compare against
        # next cycle from this sweep's telemetry.
        updated = next(ac for ac in sweep if ac.hex == current_hex)
        self._display_target_distance = updated.distance

    def _label(self, aircraft: Aircraft) -> str:
        contact = self._contacts.get(aircraft.hex)
        if contact and contact.flight != UNKNOWN:
            return contact.flight
        return aircraft.flight

    def _label_for_hex(self, hex_code: str) -> str:
        contact = self._contacts.get(hex_code)
        return contact.flight if contact else hex_code

    # --- Dispatch (called with the lock released) ---

    def _dispatch(self, events: List[TrackerEvent]) -> None:
        if not events:
            return
        with self._lock:
            handlers = list(self._handlers)
        for event in events:
            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    self.logger.error(
                        f"Tracker subscriber {getattr(handler, '__qualname__', handler)} "
                        f"failed on {type(event).__name__}: {e}"
                    )
