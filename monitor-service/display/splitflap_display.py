import re
import threading
import time
from typing import List, Optional, Sequence, Tuple

from display.base_display import Display
from models import UNKNOWN, Aircraft, StateInformation, WeatherForecast
from splitflap.config import SplitFlapConfig, parse_tokens, token_label
from splitflap.driver import SplitFlapDriver
from utils.logs import GetLogger

# Separators tried between an origin and a destination.
# Chooses the best based on what's in our character set.
_ROUTE_SEPARATORS = ("-", " ", ".")

# Alignments tried for a layout, best first. Centred reads best, but a logo
# flap only exists at the position it is bolted to, so a row that starts with
# one has to be left-aligned to reach it.
_ALIGNMENTS = ("center", "left", "right")

def _plain(value: Optional[str]) -> str:
    """A field we can lay out, or "" for the UNKNOWN sentinel and friends."""
    if not value or value == UNKNOWN:
        return ""
    # Braces are how a logo flap is named, so one arriving in a callsign from
    # the feed would be read as the start of a flap name.
    return value.strip().upper().replace("{", "").replace("}", "")

def _flap_text(value: Optional[str]) -> str:
    """Drops what no spool carries, such as the degree sign in "12°C"."""
    return re.sub(r"[^A-Z0-9 -]", "", _plain(value)).strip()

def _split_callsign(flight: str) -> Tuple[str, str]:
    """"ACA857" -> ("ACA", "857"), so the airline can go on a logo flap. ("", "") otherwise."""
    match = re.fullmatch(r"([A-Z]{3})(\d[A-Z0-9]*)", flight)
    return (match.group(1), match.group(2)) if match else ("", "")

def _layout_text(tokens: Sequence[Optional[str]]) -> str:
    """The token list as it reads on the flaps, for the log."""
    return "".join(" " if token is None else token_label(token) if len(token) > 1 else token
                   for token in tokens)

class SplitFlapDisplay(Display):
    """
    The mechanical split-flap display, as the controller sees it.

    Holds a SplitFlapDriver and decides what to put on it: the layout that fits
    this display's flaps, and whether the modules still need calibrating.
    """

    # The firmware reports its state every 2 s, so this is generous.
    CONNECT_TIMEOUT_S = 15.0

    # Homing is mechanical: up to a full turn per module, plus the search for
    # the magnet if a spool is somewhere unexpected.
    HOMING_TIMEOUT_S = 90.0

    # How long the firmware gets to answer a save with its log line.
    SAVE_TIMEOUT_S = 10.0

    def __init__(self, configManager, port: Optional[str] = None):
        self.logger = GetLogger("SplitFlap")
        self._configManager = configManager

        self._driver: Optional[SplitFlapDriver] = None
        self._rows: List[Tuple[int, int]] = []
        self._last_tokens: Optional[List[Optional[str]]] = None
        self._warned: set = set()

        # Set while calibration owns the modules. Writes are dropped rather
        # than queued during it: they would fight the offsets being measured.
        self._calibrating = threading.Event()
        self._stop = threading.Event()

        if not configManager.Get("splitflap.enabled", False):
            self.logger.info("Split-flap display is disabled in the config; nothing will be written to it.")
            return

        try:
            config = self._buildConfig()
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"The splitflap config section is unusable, so the display is off: {e}")
            return
        if config is None:
            return

        try:
            self._driver = SplitFlapDriver(config, port=port).open()
        except RuntimeError as e:
            # No pyserial, so there is nothing to talk to the display with.
            self.logger.error(f"The split-flap display is off: {e}")
            return

        self.logger.info(f"Split-flap display driver initialized ({len(config.positions)} flaps "
                         f"in {len(self._rows)} row(s)).")

        # Firmware checks and calibration need the connection, which can take a
        # while to come up — or never come up. Keep that off the caller's thread.
        threading.Thread(target=self._bringUp, name="splitflap-bringup", daemon=True).start()

    # ---- the Display interface ---------------------------------------------------------------

    def write_no_flight(self, state_info: StateInformation, forecast_data: Optional[WeatherForecast] = None):
        """Displays a 'no flights overhead' message on the split-flap."""
        self._write(self._idleLayouts(state_info, forecast_data))

    def write_flight_data(self, aircraft: Aircraft):
        """Displays flight data on the split-flap."""
        self._write(self._flightLayouts(aircraft))

    # ---- calibration -------------------------------------------------------------------------

    def IsCalibrated(self) -> bool:
        """True when home offsets have been saved to this display's flash."""
        return bool(self._configManager.Get("splitflap.calibration.calibrated", False))

    def Calibrate(self, force: bool = False) -> bool:
        """
        Calibrates the home offsets, unless that has already been done.

        The interactive per-flap procedure ("which flap is showing now?") needs
        a human and lives in splitflap/calibrate.py. What the service can
        do by itself is make every module find home and then write the offsets
        it homed to into the ESP32's flash, so the display comes back aligned
        after a power cut instead of wherever the spools happened to stop.

        Whether we have done that is remembered in the config rather than asked
        of the display: the firmware reports module state, not whether anyone
        ever saved an offset. A failed attempt leaves the flag alone, so the
        next start tries again.
        """
        if self._driver is None:
            return False
        if self.IsCalibrated() and not force:
            self.logger.debug("Split-flap is already calibrated; not calibrating again.")
            return True

        self.logger.info("Calibrating the split-flap display...")
        self._calibrating.set()
        try:
            self._driver.rehome()
            if not self._driver.wait_until_idle(timeout=self.HOMING_TIMEOUT_S):
                self.logger.error("The modules did not finish homing in time; calibration abandoned.")
                return False

            faults = self._driver.status().faults
            if faults:
                self.logger.error("Not saving a calibration while the display has faults: " + "; ".join(faults))
                return False

            saved, reply = self._saveCalibration()
            if not saved:
                self.logger.error(f"The firmware would not save the offsets: {reply}")
                return False
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            return False
        finally:
            self._calibrating.clear()
            # Anything the controller asked for while we had the modules was
            # dropped, so make the next push write it again.
            self._last_tokens = None

        self._configManager.Set("splitflap.calibration.calibrated", True)
        self._configManager.Set("splitflap.calibration.calibrated_at", time.time())
        self._configManager.SaveConfig()
        self.logger.info("Calibration saved to the display's flash.")
        return True

    def Close(self) -> None:
        """Releases the serial port. Safe to call more than once."""
        self._stop.set()
        display, self._driver = self._driver, None
        if display is not None:
            display.close()
            self.logger.info("Split-flap display closed.")

    # ---- configuration -----------------------------------------------------------------------

    def _buildConfig(self) -> Optional[SplitFlapConfig]:
        """
        The display this service is wired to, or None when there isn't one yet.

        The translation from the config file lives on SplitFlapConfig, so the
        service and the calibration tool describe the display the same way.
        """
        section = self._configManager.Get("splitflap") or {}
        if not (section.get("channels") or []):
            self.logger.warning("No splitflap.channels are configured, so the display has no flaps to write to.")
            return None

        config = SplitFlapConfig.from_service_section(section)
        self._rows = config.row_spans()
        return config

    # ---- writing -----------------------------------------------------------------------------

    @property
    def _num_positions(self) -> int:
        return self._driver.num_positions if self._driver is not None else 0

    def _write(self, layouts: Sequence[Sequence[str]]) -> None:
        """Shows the first of `layouts` that fits on the flaps we actually have."""
        if self._driver is None:
            return
        if self._calibrating.is_set():
            self.logger.debug("Calibrating, so this update was dropped.")
            return

        tokens: Optional[List[Optional[str]]] = None
        problems: List[str] = []
        for lines in layouts:
            for align in _ALIGNMENTS:
                tokens, problems = self._place(lines, align)
                if not problems:
                    break
            if not problems:
                break
        if tokens is None:
            return

        if problems:
            # Nothing fits, so the last (and plainest) layout goes up as it is:
            # a token that isn't on the spool shows the charset's fallback flap,
            # or leaves that module where it stands.
            self._warnOnce("layout", "No layout fits the configured flaps cleanly: " + "; ".join(problems))

        if tokens == self._last_tokens:
            return
        self._last_tokens = tokens
        # Already one token per position, so the driver has no padding to do.
        self._driver.show(tokens)
        self.logger.info(f"Split-flap showing: [{_layout_text(tokens)}]")

    def _place(self, lines: Sequence[str], align: str = "center") -> Tuple[List[Optional[str]], List[str]]:
        """
        Lays one string out per row of flaps.

        Returns the tokens to hand the driver (one per position, blank where a
        row doesn't reach) and what is wrong with the result: rows that are too
        long, and tokens that aren't on the spool at the position they landed
        on. A layout with no problems is one this display can show exactly.
        """
        positions = self._driver.config.positions
        tokens: List[Optional[str]] = [" "] * self._num_positions
        problems: List[str] = []

        for (start, length), line in zip(self._rows, lines):
            row = parse_tokens(line)
            if len(row) > length:
                problems.append(f"{line!r} needs {len(row)} flaps but its row has {length}")
                row = row[:length]

            pad = length - len(row)
            offset = pad // 2 if align == "center" else pad if align == "right" else 0
            for i, token in enumerate(row):
                index = start + offset + i
                if positions[index].charset.lookup(token) is None:
                    problems.append(f"{token_label(token)} is not on the flaps at position {index}")
                tokens[index] = token
        return tokens, problems

    def _flightLayouts(self, aircraft: Aircraft) -> List[List[str]]:
        """
        Layouts for one aircraft, richest first.

        Altitude, speed and heading are deliberately left out: they change on
        every sweep, and on this display every change is a row of flaps turning
        over. What goes up is the identity of the aeroplane, which doesn't move.
        """
        flight = _plain(aircraft.flight)
        airline, number = _split_callsign(flight)
        ident = flight or _plain(aircraft.reg) or _plain(aircraft.hex)
        logo = f"{{{airline}}}{number}" if airline and number else ident
        kind = _plain(aircraft.type)

        origin = _plain(aircraft.origin)
        destination = _plain(aircraft.destination)
        routes = ([f"{origin}{separator}{destination}" for separator in _ROUTE_SEPARATORS]
                  if origin and destination else [])
        if destination:
            routes.append(destination)
        routes.append("")

        names = [logo, ident] if logo != ident else [ident]
        kinds = [kind, ""] if kind else [""]
        return ([self._lines(name, route, type_name)
                 for name in names for route in routes for type_name in kinds]
                + [self._lines(ident, "", "")])

    def _idleLayouts(self, state_info: Optional[StateInformation],
                     forecast: Optional[WeatherForecast]) -> List[List[str]]:
        """Layouts for an empty sky, richest first."""
        if state_info is not None and not state_info.readsb_connected:
            headlines = ["NO RADAR", "NO RDR"]
        else:
            headlines = ["NO FLIGHTS", "NO FLTS", "NO FLT"]

        weather = self._weatherLine(forecast)
        extras = [weather, ""] if weather else [""]
        return ([self._lines(headline, extra, "") for headline in headlines for extra in extras]
                + [self._lines("", "", "")])

    def _lines(self, headline: str, second: str, third: str) -> List[str]:
        """Fits three pieces of text to however many rows of flaps there are."""
        rows = len(self._rows)
        if rows >= 3:
            return [headline, second, third]
        if rows == 2:
            return [headline, second]
        return [" ".join(part for part in (headline, second, third) if part)]

    @staticmethod
    def _weatherLine(forecast: Optional[WeatherForecast]) -> str:
        """Today's high and low, as far as the flaps can spell them."""
        if forecast is None or not forecast.forecast:
            return ""
        today = forecast.forecast[0]
        return f"{_flap_text(today.high)} {_flap_text(today.low)}".strip()

    # ---- bring-up ----------------------------------------------------------------------------

    def _bringUp(self) -> None:
        """
        Waits for the controller, reports what the firmware says, calibrates if
        it never has been, and then lets the hardware loop draw.
        """
        display = self._driver
        while display is not None and not self._stop.is_set():
            if display.wait_connected(timeout=self.CONNECT_TIMEOUT_S):
                break
            self._warnOnce("connect", "Still waiting for the split-flap controller. Check the USB cable, and that "
                                      "nothing else (web app, serial monitor) has the port open.")
        if self._stop.is_set() or self._driver is None:
            return

        firmware = display.wait_firmware(3.0)
        if firmware is not None:
            self.logger.info(f"Split-flap firmware {firmware.git_hash or '?'} ({firmware.build_date or '?'}), "
                             f"NUM_FLAPS={firmware.num_flaps or '?'}, {display.num_positions} flaps configured.")
        for problem in display.flap_count_problems():
            self.logger.error(problem)

        self.Calibrate()

    def _saveCalibration(self) -> Tuple[bool, str]:
        """
        Asks the firmware to write every module's offset to its flash and waits
        for it to say whether it did. It answers with a log line, not an ack.
        """
        replies: List[str] = []
        answered = threading.Event()

        def on_log(message: str) -> None:
            if message.startswith(("SUCCESS - saved", "ERROR - failed to save", "Can't save offsets")):
                replies.append(message)
                answered.set()

        remove = self._driver.add_log_listener(on_log)
        try:
            self._driver.save_calibration()
            answered.wait(self.SAVE_TIMEOUT_S)
        finally:
            remove()

        if not replies:
            return False, "no reply from the firmware"
        return replies[0].startswith("SUCCESS"), replies[0]

    def _warnOnce(self, key: str, message: str) -> None:
        """One log line per kind of problem; the hardware loop runs every 2 s."""
        if key not in self._warned:
            self._warned.add(key)
            self.logger.warning(message)
