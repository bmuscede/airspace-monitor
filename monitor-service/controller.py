import json
import os
import threading
import time
import uvicorn

from aircraft_database import AircraftDatabase
from config import ConfigManager
from display.dummy import DummyDisplay
from flightaware import FlightAwareClient
from state import SystemState
from utils import haversine, bearing
import logs

# Path to the dump1090 aircraft JSON feed.
AIRCRAFT_JSON_PATH = "/run/dump1090-fa/aircraft.json"

# Path to the local aircraft ICAO database CSV.
AIRCRAFT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aircraft_database.csv")


class Controller:
    def __init__(self, no_display=False):
        self.logger = logs.GetLogger("Controller")
        self.no_display = no_display

        # Core services
        self.configManager = ConfigManager()
        self.state = SystemState()
        self.aircraftDB = AircraftDatabase(AIRCRAFT_DB_PATH)

        # FlightAware client — URL and TTL come from config.
        self.flightAwareClient = FlightAwareClient(
            apiKey=self.configManager.Get("flightaware_api_key", ""),
            apiURL=self.configManager.Get("flightaware_url", ""),
            cacheTTL=self.configManager.Get("cache_ttl", 3600),
        )

        # Display drivers.
        # Use DummyDisplay when running without hardware.
        # This allows us to run on non-Raspberry Pi hardware.
        if self.no_display:
            self.logger.info("Running in no-display mode (DummyDisplay active).")
            self._dummy = DummyDisplay(mode="E-Ink")
            self.eink = self._dummy
            self.splitflap = self._dummy
        else:
            from display.eink import EInk
            from display.splitflap import SplitFlap
            self._dummy = None
            self.eink = EInk()
            self.splitflap = SplitFlap()

    def Start(self):
        """
        Starts the FastAPI web server and the hardware monitoring thread.
        
        The web server runs in a daemon thread so that when the main
        thread (hardware loop) exits, the process shuts down cleanly.
        """
        self.logger.info("Starting Airspace Monitor controller...")

        # Wire up the API module with a reference to this controller.
        import api
        api.controller = self

        # Start the FastAPI server in a background daemon thread.
        web_thread = threading.Thread(target=self._start_webserver, daemon=True)
        web_thread.start()

        # Run the hardware loop on the main thread.
        # This blocks forever until systemRunning is set to False.
        self._hardware_loop()

    def _start_webserver(self):
        """Runs the FastAPI/Uvicorn server on port 8000."""
        self.logger.info("Starting web server on 0.0.0.0:8000...")
        import api
        uvicorn.run(api.app, host="0.0.0.0", port=8000, log_level="warning")

    def _hardware_loop(self):
        """
        Continuously polls dump1090 for aircraft data, enriches it,
        applies sticky-closest logic, and pushes to the active display.
        """
        self.logger.info("Hardware loop started.")
        self.state.system_running = True
        
        while self.state.system_running:
            try:
                # 1. Read aircraft from dump1090
                aircraft_list = self._read_aircraft()
                
                # 2. Enrich with aircraft type/registration from the local DB
                for ac in aircraft_list:
                    info = self.aircraftDB.GetAircraftInfo(ac.get("hex", ""))
                    ac["type"] = info.get("type", "???")
                    ac["reg"] = info.get("reg", "???")

                # 3. Apply sticky-closest logic to pick the display aircraft
                closest = self._pick_closest(aircraft_list)
                
                # 4. Update shared state (thread-safe)
                self.state.update_aircraft(aircraft_list, closest)
                
                # 5. If we have a display target, resolve its route via FlightAware
                display_ac = self.state.current_aircraft
                if display_ac and display_ac.get("flight", "???") != "???":
                    origin, dest = self.flightAwareClient.GetRoute(display_ac["flight"])
                    display_ac["origin"] = origin
                    display_ac["destination"] = dest
                    self.state.current_aircraft = display_ac

                # 6. Push to the active display
                self._push_to_display(self.state.current_aircraft)
                
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Hardware loop error: {e}")
                time.sleep(5)
        
        self.logger.info("Hardware loop stopped.")

    def _read_aircraft(self):
        """
        Reads /run/dump1090-fa/aircraft.json, parses it, calculates
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
            aircraft_list.append({
                "hex": ac.get("hex", "").strip().lower(),
                "flight": flight_raw if flight_raw else "???",
                "altitude": ac.get("alt_baro", 0),
                "speed": ac.get("gs", 0),
                "heading": ac.get("track", 0),
                "lat": lat,
                "lon": lon,
                "distance": round(dist, 1),
                "bearing": bear,
                "origin": "???",
                "destination": "???",
                "type": "???",
                "reg": "???",
            })

        # Sort by distance so closest is first.
        aircraft_list.sort(key=lambda x: x["distance"])
        return aircraft_list

    def _pick_closest(self, aircraft_list):
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
            self.logger.info(f"Displaying new aircraft: {closest.get('flight', '???')}")
            return closest

        # Check if the currently displayed aircraft is still in this cycle's list.
        current_hex = current.get("hex", "")
        still_in_range = any(ac["hex"] == current_hex for ac in aircraft_list)

        if not still_in_range:
            # Current aircraft left range — switch to closest.
            self.state.current_aircraft = closest
            self.logger.info(
                f"Aircraft {current.get('flight', '???')} left range. "
                f"Switching to {closest.get('flight', '???')}."
            )
            return closest

        if closest["hex"] != current_hex and closest["distance"] < current.get("distance", 9999):
            # A different aircraft is now strictly closer — switch.
            self.state.current_aircraft = closest
            self.logger.info(
                f"New closer aircraft detected: {closest.get('flight', '???')} "
                f"({closest['distance']} nm vs {current.get('distance', '???')} nm)."
            )
            return closest

        # Otherwise, keep the current aircraft (update its telemetry).
        updated = next((ac for ac in aircraft_list if ac["hex"] == current_hex), current)
        self.state.current_aircraft = updated
        return closest

    def _push_to_display(self, aircraft):
        """
        Sends the current aircraft to the active display driver.
        """
        mode = self.state.display_mode
        driver = self.eink if mode == "E-Ink" else self.splitflap

        if aircraft is None:
            driver.WriteNoFlight()
            return

        driver.WriteFlightData(
            flightNum=aircraft.get("flight", "???"),
            origin=aircraft.get("origin", "???"),
            dest=aircraft.get("destination", "???"),
            elev=aircraft.get("altitude"),
            heading=aircraft.get("heading"),
            gs=aircraft.get("speed"),
            aircraftType=aircraft.get("type", "???"),
        )

    def GetAircraft(self):
        """Returns all aircraft currently tracked (for the dashboard)."""
        return self.state.all_aircraft

    def GetState(self):
        """Returns a snapshot of the full system state."""
        return self.state.snapshot()

    def ToggleDisplayMode(self):
        """Switches between E-Ink and Split-Flap. Returns the new mode."""
        new_mode = self.state.toggle_display_mode()
        self.logger.info(f"Display mode switched to {new_mode}.")

        # If running in no-display mode, tell the dummy which display to act as.
        if self._dummy is not None:
            self._dummy.SetMode(new_mode)

        return new_mode

    def Shutdown(self):
        """Gracefully shuts down the hardware loop."""
        self.logger.info("Shutdown requested.")
        self.state.system_running = False