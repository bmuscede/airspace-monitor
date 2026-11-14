from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import List, Optional, Union

# Sentinel used throughout the service for "we don't know this yet".
# ADS-B gives us position long before it gives us identity, and the local
# aircraft database / FlightAware fill in the rest later (or never), so every
# identity field has to have a well-known "unset" value.
UNKNOWN = "???"

class Aircraft(BaseModel):
    hex: str = Field(description="ICAO 24-bit address")
    flight: str = UNKNOWN
    altitude: int = 0
    speed: int = 0
    heading: int = 0
    lat: float = 0.0
    lon: float = 0.0
    distance: float = 0.0
    bearing: float = 0.0
    origin: str = UNKNOWN
    destination: str = UNKNOWN
    type: str = UNKNOWN
    reg: str = UNKNOWN

class WeatherDay(BaseModel):
    day: str
    high: str
    low: str
    description: str
    icon: str

class WeatherForecast(BaseModel):
    city_name: str
    location_name: str
    forecast: List[WeatherDay]

class StateInformation(BaseModel):
    readsb_connected: bool
    range: int
    uptime: str
    daily_seen: int
    total_seen: int

class SystemStateSnapshot(BaseModel):
    systemRunning: bool
    displayMode: str
    currentAircraft: Optional[Aircraft] = None
    closestAircraft: Optional[Aircraft] = None
    aircraftCount: int
    lastUpdate: float
    readsbConnected: bool

class Contact(BaseModel):
    """
    One aircraft's *visit* to our airspace: from first detection until the
    receiver stops hearing it for longer than the gap timeout.

    A contact is the unit of track continuity. Unlike a raw Aircraft (which is
    a single radar sweep's worth of telemetry) a Contact spans many sweeps and
    accumulates the things that are only meaningful over a whole visit:
    closest approach, altitude/speed extremes, and the best identity we ever
    managed to resolve.

    Owned exclusively by ContactTracker. It carries no database id on purpose —
    persistence is HistoryStore's problem and must not leak in here.
    """

    hex: str = Field(description="ICAO 24-bit address; the track's identity")
    first_seen: float
    last_seen: float

    # Latest telemetry sweep for this track. Always the newest values.
    aircraft: Aircraft

    # Closest approach over the life of the visit.
    closest_nm: float
    closest_at: Optional[float] = None
    closest_bearing: Optional[float] = None

    # Envelope over the life of the visit.
    min_altitude: Optional[int] = None
    max_altitude: Optional[int] = None
    max_speed: Optional[int] = None

    sample_count: int = 0

    # Best-known identity. These are *sticky*: once we learn a real value we
    # keep it, even if later sweeps come back as UNKNOWN. Identity arrives late
    # and inconsistently (readsb hardcodes UNKNOWN for type/reg, FlightAware
    # enrichment only fires once per contact), so the last sweep is routinely
    # less identified than what we knew mid-visit.
    flight: str = UNKNOWN
    registration: str = UNKNOWN
    aircraft_type: str = UNKNOWN
    origin: str = UNKNOWN
    destination: str = UNKNOWN

    def to_aircraft(self) -> Aircraft:
        """
        Latest telemetry with the best-known identity overlaid.

        This is what external callers (the API, the displays) should see: the
        current position of the aircraft, labelled with everything we have ever
        managed to learn about it rather than only what this sweep carried.
        """
        merged = self.aircraft.model_copy()
        merged.flight = self.flight
        merged.origin = self.origin
        merged.destination = self.destination
        merged.type = self.aircraft_type
        merged.reg = self.registration
        return merged


# --- Tracker events -------------------------------------------------------
#
# The event contract is the load-bearing interface for later phases: Phase 3
# streams these over SSE and Phase 4 dead-reckons between them. Plain
# dataclasses rather than Pydantic models — these are dispatched once per
# aircraft per cycle on the hardware thread, and there is nothing to validate.
#
# Handlers receive the tracker's *live* Contact object (except on close, where
# the tracker has already dropped it). They run on the hardware thread with the
# tracker lock released and must treat the contact as read-only and not retain
# a reference beyond the call.

@dataclass
class ContactOpened:
    """A hex we have not seen within the gap window has appeared."""
    contact: Contact

@dataclass
class ContactUpdated:
    """
    Telemetry refresh on a track we already hold.

    `previous` is the Aircraft the contact carried before this sweep, so a
    subscriber can compute deltas without keeping its own shadow copy. Phase 3
    needs this to emit position deltas instead of full snapshots.
    """
    contact: Contact
    previous: Aircraft

@dataclass
class ContactClosed:
    """
    The visit is over: gap timeout exceeded, or a clean shutdown flushed it.
    Carries the completed record — this is the one worth writing to disk.
    """
    contact: Contact

TrackerEvent = Union[ContactOpened, ContactUpdated, ContactClosed]
