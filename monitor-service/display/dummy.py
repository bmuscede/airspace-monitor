import logs


class DummyDisplay:
    """
    A software-only display driver used when --no-display is passed.
    
    Substitutes for both EInk and SplitFlap so the controller can run
    on a dev machine without any SPI/I2C hardware present. Logs what
    it would render and which display mode it is acting as.
    """

    def __init__(self, mode: str = "E-Ink"):
        self.logger = logs.GetLogger("DummyDisplay")
        self._mode = mode
        self.logger.info(f"Dummy display initialized (acting as {self._mode}).")
        self._last_state = None

    def SetMode(self, mode: str):
        """Switches which hardware display this dummy is impersonating."""
        self._mode = mode
        self.logger.info(f"Now acting as {self._mode}.")

    def WriteNoFlight(self):
        """Logs a 'no flights overhead' message."""
        if self._last_state == "NO_FLIGHT":
            return
            
        self.logger.info(
            f"[Acting as {self._mode}] NO FLIGHTS OVERHEAD — "
            f"Cannot detect any ADS-B signals. Waiting on data..."
        )
        self._last_state = "NO_FLIGHT"

    def WriteFlightData(self, flightNum, origin, dest, elev, heading, gs, aircraftType):
        """Logs the flight data that would be rendered on the real display."""
        flight_state = (flightNum, origin, dest, elev, heading, gs, aircraftType)
        if self._last_state == flight_state:
            return
            
        self.logger.info(
            f"[Acting as {self._mode}] "
            f"{flightNum} OVERHEAD | {origin} > {dest} | "
            f"ALT:{elev} HDG:{heading} SPD:{gs} TYPE:{aircraftType}"
        )
        self._last_state = flight_state
