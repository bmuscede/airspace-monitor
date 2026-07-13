from pydantic import BaseModel, Field
from typing import List, Optional

class Aircraft(BaseModel):
    hex: str = Field(description="ICAO 24-bit address")
    flight: str = "???"
    altitude: int = 0
    speed: int = 0
    heading: int = 0
    lat: float = 0.0
    lon: float = 0.0
    distance: float = 0.0
    bearing: float = 0.0
    origin: str = "???"
    destination: str = "???"
    type: str = "???"
    reg: str = "???"

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
