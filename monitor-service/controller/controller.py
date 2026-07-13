import json
import os
import threading
import time
import uvicorn
import sys
from typing import List, Optional

from controller.state import SystemState
from data.aircraft_database import AircraftDatabase
from data.flightaware import FlightAwareClient
from data.openweathermap import OpenweathermapClient
from display.dev import DevDisplay
from utils.config import ConfigManager
from utils.logs import GetLogger
from utils.utils import haversine, bearing
from models import Aircraft, StateInformation


# Path to the readsb aircraft JSON feed.
AIRCRAFT_JSON_PATH = "/run/readsb/aircraft.json"

# Path to the local aircraft ICAO database CSV.
AIRCRAFT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aircraft_database.csv")

# Sleep intervals.
DEV_MODE_SLEEP=30
RPI_MODE_SLEEP=2

class Controller:
    def __init__(self, configDir: str, devMode: bool = False):
        self.logger = GetLogger("Controller")
        self.devMode = devMode

        # Initialize the core libraries.
        self.configManager = ConfigManager(configDir)
        self.state = SystemState()
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

        # Display drivers.
        # Use DevDisplay when running without hardware.
        # This allows us to run on non-Raspberry Pi hardware.
        if self.devMode:
            self.logger.info("Running in development mode...")
            self._devDisplay = DevDisplay(mode="E-Ink")
            self.eink = self._devDisplay
            self.splitflap = self._devDisplay
        else:
            from display.eink import EInk
            from display.splitflap import SplitFlap
            self._devDisplay = None
            self.eink = EInk()
            self.splitflap = SplitFlap()

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

        # Start the FastAPI server in a background daemon thread.
        web_thread = threading.Thread(target=self._start_webserver, daemon=True)
        web_thread.start()

        # Run the hardware loop on the main thread.
        # This blocks forever until systemRunning is set to False.
        self._hardware_loop()

    def _start_webserver(self) -> None:
        """Runs the FastAPI/Uvicorn server on port 8000."""
        self.logger.info("Starting web server on 0.0.0.0:8000...")
        import controller.api
        uvicorn.run(controller.api.app, host="0.0.0.0", port=8000, log_level="warning")

    def _hardware_loop(self) -> None:
        """
        Continuously polls dump1090 for aircraft data, enriches it,
        applies sticky-closest logic, and pushes to the active display.
        """
        self.logger.info("Hardware loop started.")
        self.state.system_running = True
        
        while self.state.system_running:
            try:
                # Read the list of aircraft detected in the current area.
                aircraft_list = self._read_aircraft() if not self.devMode else self._read_aircraft_dev()
                
                # Use the local DB to get other aircraft information.
                for ac in aircraft_list:
                    if ac.type == "???":
                        info = self.aircraftDB.GetAircraftInfo(ac.hex)
                        ac.type = info.get("type", "???")
                        ac.reg = info.get("reg", "???")

                # Pick the closest aircraft using other logic.
                closest = self._pick_closest(aircraft_list)
                
                # Update our entire aircraft list.
                self.state.update_aircraft(aircraft_list, closest)
                
                # If we have a display target, resolve its route via FlightAware or our cache.
                display_ac = self.state.current_aircraft
                if display_ac and display_ac.flight != "???":
                    origin, dest = self.flightAwareClient.GetRoute(display_ac.flight)
                    display_ac.origin = origin
                    display_ac.destination = dest
                    self.state.current_aircraft = display_ac

                # Push to the active display
                self._push_to_display(self.state.current_aircraft)
                
                # Figure out our sleep time.
                # Sleep for longer in dev mode versus regular hardware run.
                sleepTime = DEV_MODE_SLEEP if self.devMode else RPI_MODE_SLEEP
                time.sleep(sleepTime)
                
            except Exception as e:
                self.logger.error(f"Hardware loop error: {e}")
                time.sleep(5)
        
        self.logger.info("Hardware loop stopped.")

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
                flight=flight_raw if flight_raw else "???",
                altitude=ac.get("alt_baro", 0) or 0,
                speed=ac.get("gs", 0) or 0,
                heading=ac.get("track", 0) or 0,
                lat=lat,
                lon=lon,
                distance=round(dist, 1),
                bearing=bear,
                origin="???",
                destination="???",
                type="???",
                reg="???",
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
        
        self.logger.info(f"Simulating radar sweep via FlightAware ({max_range} NM)...")
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
                flight=ident if ident else "???",
                altitude=alt,
                speed=spd_raw or 0,
                heading=hdg_raw or 0,
                lat=lat,
                lon=lon,
                distance=round(dist, 1),
                bearing=bear,
                origin="???",
                destination="???",
                type=ac.get("aircraft_type", "???"),
                reg=ac.get("registration", "???"),
            ))

        aircraft_list.sort(key=lambda x: x.distance)
        self.state.readsb_connected = True 
        return aircraft_list  

    def _pick_closest(self, aircraft_list: List[Aircraft]) -> Optional[Aircraft]:
        """
        Implements the sticky-closest strategy:
        
        1. If nothing is currently displayed, pick the closest.
        2. If the currently displayed aircraft is still in range, keep it.
        3. Only switch when a new aircraft becomes strictly closer.
        4. If the displayed aircraft leaves range, fall back to next closest.
        """
        if not aircraft_list:
            self.state.current_aircraft = None
            return None

        closest = aircraft_list[0]  # Already sorted by distance
        current = self.state.current_aircraft

        if current is None:
            # Nothing displayed yet — pick the closest.
            self.state.current_aircraft = closest
            self.logger.info(f"Displaying new aircraft: {closest.flight}")
            return closest

        # Check if the currently displayed aircraft is still in this cycle's list.
        current_hex = current.hex
        still_in_range = any(ac.hex == current_hex for ac in aircraft_list)

        if not still_in_range:
            # Current aircraft left range — switch to closest.
            self.state.current_aircraft = closest
            self.logger.info(
                f"Aircraft {current.flight} left range. "
                f"Switching to {closest.flight}."
            )
            return closest

        if closest.hex != current_hex and closest.distance < current.distance:
            # A different aircraft is now strictly closer — switch.
            self.state.current_aircraft = closest
            self.logger.info(
                f"New closer aircraft detected: {closest.flight} "
                f"({closest.distance} nm vs {current.distance} nm)."
            )
            return closest

        # Otherwise, keep the current aircraft (update its telemetry).
        updated = next((ac for ac in aircraft_list if ac.hex == current_hex), current)
        self.state.current_aircraft = updated
        return closest

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
            state_info = StateInformation(
                readsb_connected=self.state.readsb_connected,
                range=self.configManager.Get("max_radar_range_nm", 50),
                uptime=self.state.uptime,
                daily_seen=self.state.daily_aircraft_seen,
                total_seen=self.state.total_aircraft_seen
            )
            driver.WriteNoFlight(state_info, forecast)
            return

        driver.WriteFlightData(aircraft)

    def GetAircraft(self) -> List[Aircraft]:
        """Returns all aircraft currently tracked (for the dashboard)."""
        return self.state.all_aircraft

    def GetState(self) -> dict:
        """Returns a snapshot of the full system state."""
        return self.state.snapshot()

    def ToggleDisplayMode(self) -> str:
        """Switches between E-Ink and Split-Flap. Returns the new mode."""
        new_mode = self.state.toggle_display_mode()
        self.logger.info(f"Display mode switched to {new_mode}.")

        # If running in no-display mode, tell the dev display which display to act as.
        if self._devDisplay is not None:
            self._devDisplay.SetMode(new_mode)

        return new_mode

    def Shutdown(self) -> None:
        """Gracefully shuts down the hardware loop."""
        self.logger.info("Shutdown requested.")
        self.state.system_running = False