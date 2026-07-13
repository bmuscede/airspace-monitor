from typing import Optional

from display.base_display import Display
from models import Aircraft, StateInformation, WeatherForecast
from utils.logs import GetLogger

class SplitFlapDisplay(Display):
    """
    Stub driver for the mechanical Split-Flap display.
    
    Mirrors the interface of EInk so the controller can swap
    between display drivers without branching logic.
    
    TODO: Implement real I2C communication with MCP23017
    expanders and stepper motor controllers.
    """

    def __init__(self):
        self.logger = GetLogger("SplitFlap")
        self.logger.info("Split-Flap display driver initialized (STUB).")
        self._last_state = None

    def write_no_flight(self, state_info: StateInformation, forecast_data: Optional[WeatherForecast] = None):
        """Displays a 'no flights overhead' message on the split-flap."""
        if self._last_state == "NO_FLIGHT":
            return
            
        self.logger.info("STUB: Would display 'NO FLIGHTS OVERHEAD' on Split-Flap.")
        self._last_state = "NO_FLIGHT"

    def write_flight_data(self, aircraft: Aircraft):
        """Displays flight data on the split-flap."""
        flight_state = (aircraft.flight, aircraft.origin, aircraft.destination, aircraft.altitude, aircraft.heading, aircraft.speed, aircraft.type)
        if self._last_state == flight_state:
            return
            
        self.logger.info(
            f"STUB: Would display on Split-Flap: "
            f"{aircraft.flight} | {aircraft.origin} -> {aircraft.destination} | "
            f"ALT:{aircraft.altitude} HDG:{aircraft.heading} SPD:{aircraft.speed} TYPE:{aircraft.type}"
        )
        self._last_state = flight_state
