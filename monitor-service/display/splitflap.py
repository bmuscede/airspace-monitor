from utils.logs import GetLogger

class SplitFlap:
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

    def WriteNoFlight(self):
        """Displays a 'no flights overhead' message on the split-flap."""
        if self._last_state == "NO_FLIGHT":
            return
            
        self.logger.info("STUB: Would display 'NO FLIGHTS OVERHEAD' on Split-Flap.")
        self._last_state = "NO_FLIGHT"

    def WriteFlightData(self, flightNum, origin, dest, elev, heading, gs, aircraftType):
        """Displays flight data on the split-flap."""
        flight_state = (flightNum, origin, dest, elev, heading, gs, aircraftType)
        if self._last_state == flight_state:
            return
            
        self.logger.info(
            f"STUB: Would display on Split-Flap: "
            f"{flightNum} | {origin} -> {dest} | "
            f"ALT:{elev} HDG:{heading} SPD:{gs} TYPE:{aircraftType}"
        )
        self._last_state = flight_state
