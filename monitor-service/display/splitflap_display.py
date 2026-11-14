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

#!/usr/bin/env python3
"""
splitflap_display.py - drive Scott Bezek's splitflap display (Chainlink + ESP32 firmware) from Python.

Speaks the firmware's protobuf-over-serial protocol directly (COBS framing + CRC32), the same
protocol Scott's web app uses. The only dependency is pyserial:

    pip install pyserial

What it does
  * Per-position character sets, including multi-character tokens for logo flaps
    (write "{ACA}" to show an Air Canada flap) and aliases (e.g. ROU -> ACA).
  * Maps display positions (left to right) to physical Chainlink channels, so gaps in the
    driver channels are fine. Unused channels are ignored.
  * Tracks each module's state (NORMAL / LOOK_FOR_HOME / SENSOR_ERROR / PANIC / DISABLED),
    home-sensor error counters, loopback health and firmware build info.
  * Optionally re-homes modules that fall into SENSOR_ERROR (rate limited, then gives up).
  * Reconnects if the USB port drops and re-sends the display contents if the ESP32 restarts.
  * Interactive calibration (same procedure as Scott's web app), saved to the ESP32's flash.

Command line
    python splitflap_display.py ports                    # list serial ports
    python splitflap_display.py status [--watch]         # module states, sensor counters, firmware
    python splitflap_display.py show "HELLO"             # write text
    python splitflap_display.py show "{ACA}857"          # {NAME} = a multi-character (logo) flap
    python splitflap_display.py type                     # type lines interactively
    python splitflap_display.py calibrate [POS ...]      # calibrate home offsets, then save
    python splitflap_display.py cycle                    # step every module through every flap
    python splitflap_display.py rehome [POS ...]         # clear errors and find home again
    python splitflap_display.py reset                    # hard-reset the ESP32

    Options: --config FILE (default ./splitflap_config.json), --port PORT, -v

As a library
    from splitflap_display import DisplayConfig, SplitflapDisplay

    config = DisplayConfig.load("splitflap_config.json")
    with SplitflapDisplay(config) as display:
        display.wait_connected()
        display.show_text("{ACA}857")      # or display.show(["ACA", "8", "5", "7"])
        display.wait_until_idle()
        print(display.status().text, display.status().faults)

    show()/show_text() never block; they queue the change and return. Status listeners
    (add_listener) are called from the I/O thread, so keep them quick.

Notes
  * Only one program can have the serial port open: close the web app / PlatformIO serial
    monitor first.
  * The firmware's NUM_FLAPS (firmware/src/config.h) must match the number of flaps on your
    spools. Every charset in the config must have exactly that many entries.
  * The firmware only remembers the last controller's settings, so when this script first
    connects some modules may make one full turn.
"""

from __future__ import annotations

import argparse
import collections
import enum
import json
import logging
import os
import random
import struct
import sys
import threading
import time
import zlib
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, Iterable, Iterator, List, NamedTuple, Optional, Sequence, Tuple, Union

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # reported when a port is actually needed
    serial = None

__all__ = [
    "Charset",
    "DisplayConfig",
    "DisplayStatus",
    "FirmwareInfo",
    "ModuleState",
    "ModuleStatus",
    "PositionConfig",
    "SplitflapDisplay",
    "find_port",
    "parse_tokens",
]

log = logging.getLogger("splitflap")
device_log = logging.getLogger("splitflap.device")

BAUD = 230400
RETRY_INTERVAL_S = 0.25          # same retry interval as Scott's Python/JS libraries
SILENCE_POKE_S = 6.0             # firmware sends GeneralState every 2 s; silence means legacy mode or a reboot
LEGACY_40_FLAPS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'"   # "Flap option 1" in firmware/src/config.h

# USB serial bridges used by ESP32 boards / the T-Display (same list as Scott's web app)
KNOWN_USB_IDS = {
    (0x10C4, 0xEA60),  # Silicon Labs CP210x
    (0x1A86, 0x55D4),  # QinHeng CH9102
}


# ---------------------------------------------------------------------------------------------
# Wire format: COBS framing, CRC32 and the handful of protobuf messages in proto/splitflap.proto
# ---------------------------------------------------------------------------------------------

def cobs_encode(data: bytes) -> bytes:
    """Consistent Overhead Byte Stuffing (without the trailing 0x00 delimiter)."""
    out = bytearray()
    block = bytearray()
    need_final = True
    for b in data:
        if b == 0:
            out.append(len(block) + 1)
            out += block
            block.clear()
            need_final = True
        else:
            block.append(b)
            if len(block) == 254:
                out.append(0xFF)
                out += block
                block.clear()
                need_final = False
    if block or need_final:
        out.append(len(block) + 1)
        out += block
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        code = data[i]
        if code == 0:
            raise ValueError("zero byte inside COBS frame")
        end = i + code
        if end > n:
            raise ValueError("truncated COBS frame")
        chunk = data[i + 1:end]
        if 0 in chunk:
            raise ValueError("zero byte inside COBS frame")
        out += chunk
        i = end
        if code != 0xFF and i < n:
            out.append(0)
    return bytes(out)


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(buf: bytes, pos: int) -> Tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated varint")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")


def _pb_uint(field_no: int, value: int) -> bytes:
    """A varint field (uint32/bool/enum). proto3 leaves out zero values."""
    if not value:
        return b""
    return _varint(field_no << 3) + _varint(int(value))


def _pb_msg(field_no: int, body: bytes) -> bytes:
    """A length-delimited field (sub-message, string or bytes). Always written, even if empty."""
    return _varint((field_no << 3) | 2) + _varint(len(body)) + body


def _pb_fields(buf: bytes) -> Iterator[Tuple[int, int, Union[int, bytes]]]:
    pos, n = 0, len(buf)
    while pos < n:
        key, pos = _read_varint(buf, pos)
        field_no, wire_type = key >> 3, key & 7
        if wire_type == 0:
            value, pos = _read_varint(buf, pos)
        elif wire_type == 2:
            length, pos = _read_varint(buf, pos)
            value = buf[pos:pos + length]
            pos += length
        elif wire_type == 1:
            value = buf[pos:pos + 8]
            pos += 8
        elif wire_type == 5:
            value = buf[pos:pos + 4]
            pos += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire_type}")
        if pos > n:
            raise ValueError("truncated protobuf message")
        yield field_no, wire_type, value


class _Action(enum.IntEnum):
    """SplitflapCommand.ModuleCommand.Action"""
    NO_OP = 0
    GO_TO_FLAP = 1
    RESET_AND_HOME = 2
    INCREASE_OFFSET_TENTH = 90
    INCREASE_OFFSET_HALF = 91
    SET_OFFSET = 92


class ModuleState(enum.IntEnum):
    """SplitflapState.ModuleState.State"""
    NORMAL = 0
    LOOK_FOR_HOME = 1
    SENSOR_ERROR = 2   # couldn't find the home sensor and gave up; needs a re-home
    PANIC = 3          # firmware bug detected; needs an ESP32 reset
    DISABLED = 4       # disabled, e.g. after a Chainlink loopback failure; needs an ESP32 reset
    UNKNOWN = 255      # not part of the protocol; used for values this script doesn't know


def _to_module_state(value: int) -> ModuleState:
    try:
        return ModuleState(value)
    except ValueError:
        return ModuleState.UNKNOWN


def _encode_config(modules: Sequence[Tuple[int, int, int]]) -> bytes:
    """SplitflapConfig. One (target_flap_index, movement_nonce, reset_nonce) per channel."""
    body = bytearray()
    for target, movement_nonce, reset_nonce in modules:
        body += _pb_msg(1, _pb_uint(1, target) + _pb_uint(2, movement_nonce) + _pb_uint(3, reset_nonce))
    return bytes(body)


def _encode_command(actions: Sequence[Tuple[_Action, int]], save_all_offsets: bool = False) -> bytes:
    """SplitflapCommand. One (action, param) per channel, starting at channel 0."""
    body = bytearray()
    for action, param in actions:
        body += _pb_msg(2, _pb_uint(1, int(action)) + _pb_uint(2, param))
    if save_all_offsets:
        body += _pb_uint(3, 1)
    return bytes(body)


class _RawModule(NamedTuple):
    state: int
    flap_index: int
    moving: bool
    home_state: bool
    count_unexpected_home: int
    count_missed_home: int


def _decode_module_state(buf: bytes) -> _RawModule:
    values = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for field_no, wire_type, value in _pb_fields(buf):
        if wire_type == 0 and field_no in values:
            values[field_no] = value
    return _RawModule(values[1], values[2], bool(values[3]), bool(values[4]), values[5], values[6])


def _decode_splitflap_state(buf: bytes) -> Tuple[List[_RawModule], bool]:
    modules: List[_RawModule] = []
    loopbacks_ok = False
    for field_no, wire_type, value in _pb_fields(buf):
        if field_no == 1 and wire_type == 2:
            modules.append(_decode_module_state(value))
        elif field_no == 2 and wire_type == 0:
            loopbacks_ok = bool(value)
    return modules, loopbacks_ok


@dataclass(frozen=True)
class FirmwareInfo:
    protocol_version: int
    uptime_ms: int
    git_hash: str
    build_date: str
    build_os: str
    flap_charset: str     # the firmware's `flaps` array (only used by the T-Display and web app)

    @property
    def num_flaps(self) -> int:
        """NUM_FLAPS the firmware was built with (0 if the firmware is too old to report it)."""
        return len(self.flap_charset)


def _decode_general_state(buf: bytes) -> FirmwareInfo:
    version = uptime = 0
    git_hash = build_date = build_os = ""
    charset = b""
    for field_no, wire_type, value in _pb_fields(buf):
        if field_no == 1 and wire_type == 0:
            version = value
        elif field_no == 2 and wire_type == 0:
            uptime = value
        elif field_no == 3 and wire_type == 2:
            for b_field, b_wire, b_value in _pb_fields(value):
                if b_wire != 2:
                    continue
                text = bytes(b_value).decode("utf-8", "replace")
                if b_field == 1:
                    git_hash = text
                elif b_field == 2:
                    build_date = text
                elif b_field == 3:
                    build_os = text
        elif field_no == 4 and wire_type == 2:
            charset = bytes(value)
    return FirmwareInfo(version, uptime, git_hash, build_date, build_os, charset.decode("latin-1"))


def _decode_from_splitflap(buf: bytes):
    """FromSplitflap -> (kind, value)."""
    for field_no, wire_type, value in _pb_fields(buf):
        if wire_type != 2:
            continue
        if field_no == 1:
            return "state", _decode_splitflap_state(value)
        if field_no == 2:
            text = ""
            for f, w, v in _pb_fields(value):
                if f == 1 and w == 2:
                    text = bytes(v).decode("utf-8", "replace")
            return "log", text
        if field_no == 3:
            nonce = 0
            for f, w, v in _pb_fields(value):
                if f == 1 and w == 0:
                    nonce = v
            return "ack", nonce
        if field_no == 4:
            return "supervisor", None   # Chainlink Base only
        if field_no == 5:
            return "general", _decode_general_state(value)
    return "unknown", None


# ---------------------------------------------------------------------------------------------
# Character sets and configuration
# ---------------------------------------------------------------------------------------------

_DEFAULT = object()


class Charset:
    """The flaps on one kind of module, in the order they fall when the spool turns forward.

    Index 0 is the home flap (the one the module shows after calibration + homing).
    A flap is named by a token: a single character, or a longer name for logo/symbol flaps.
    """

    def __init__(self, name: str, flaps: Union[str, Sequence[str]], aliases: Optional[Dict[str, str]] = None,
                 fallback=_DEFAULT):
        flap_list = list(flaps)
        if not flap_list:
            raise ValueError(f"charset {name!r} has no flaps")
        for token in flap_list:
            if not isinstance(token, str) or not token:
                raise ValueError(f"charset {name!r}: every flap must be a non-empty string (got {token!r})")
        self.name = name
        self.flaps: Tuple[str, ...] = tuple(flap_list)
        self._index: Dict[str, int] = {}
        for i, token in enumerate(self.flaps):
            self._index.setdefault(token, i)
        self.aliases: Dict[str, str] = dict(aliases or {})
        for alias, target in self.aliases.items():
            if target not in self._index:
                raise ValueError(f"charset {name!r}: alias {alias!r} points at {target!r}, which isn't one of its flaps")
        if fallback is _DEFAULT:
            fallback = " " if " " in self._index else None
        elif fallback is not None and self.lookup(fallback) is None:
            raise ValueError(f"charset {name!r}: fallback {fallback!r} isn't one of its flaps")
        self.fallback: Optional[str] = fallback

    def __len__(self) -> int:
        return len(self.flaps)

    def __repr__(self) -> str:
        return f"Charset({self.name!r}, {len(self.flaps)} flaps)"

    def lookup(self, token: str) -> Optional[int]:
        """Flap index for a token (exact, then alias, then upper-case), or None."""
        for candidate in (token, token.upper()):
            if candidate in self._index:
                return self._index[candidate]
            target = self.aliases.get(candidate)
            if target is not None:
                return self._index[target]
        return None

    def resolve(self, token: str) -> Optional[int]:
        """Like lookup(), but falls back to the fallback flap. None means 'leave the module alone'."""
        index = self.lookup(token)
        if index is None and self.fallback is not None:
            index = self.lookup(self.fallback)
        return index

    def token(self, index: int) -> Optional[str]:
        return self.flaps[index] if 0 <= index < len(self.flaps) else None


def parse_tokens(text: str) -> List[str]:
    """Split text into flap tokens. "{ACA}857" -> ["ACA", "8", "5", "7"]. Use "{{" / "}}" for braces."""
    tokens: List[str] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "{":
            if text.startswith("{{", i):
                tokens.append("{")
                i += 2
                continue
            end = text.find("}", i + 1)
            if end == -1:
                raise ValueError(f"unclosed '{{' in {text!r}")
            name = text[i + 1:end]
            if not name:
                raise ValueError(f"empty '{{}}' in {text!r}")
            tokens.append(name)
            i = end + 1
        elif c == "}" and text.startswith("}}", i):
            tokens.append("}")
            i += 2
        else:
            tokens.append(c)
            i += 1
    return tokens


def _token_label(token: Optional[str]) -> str:
    if token is None:
        return "?"
    if token == " ":
        return "(blank)"
    return token if len(token) == 1 else "{" + token + "}"


@dataclass(frozen=True)
class PositionConfig:
    channel: int          # Chainlink channel: driver 1 = 0..5 (A..F), driver 2 = 6..11, ...
    charset: Charset


@dataclass
class DisplayConfig:
    positions: List[PositionConfig]            # display positions, left to right as seen from the front
    port: Optional[str] = None                 # None = auto-detect
    auto_rehome: bool = True
    max_rehome_attempts: int = 3               # per module, within rehome_window_s
    rehome_window_s: float = 600.0
    rehome_backoff_s: float = 15.0             # minimum time between attempts on one module

    def __post_init__(self):
        channels = [p.channel for p in self.positions]
        if len(set(channels)) != len(channels):
            raise ValueError(f"each channel can only be used by one position (got {channels})")
        for ch in channels:
            if not 0 <= ch < 255:
                raise ValueError(f"channel {ch} is out of range")
        lengths = sorted({len(p.charset) for p in self.positions})
        if len(lengths) > 1:
            log.warning("Charsets have different lengths %s, but the firmware uses one NUM_FLAPS for every "
                        "module. Every charset should have exactly NUM_FLAPS flaps.", lengths)

    @classmethod
    def from_dict(cls, data: dict) -> "DisplayConfig":
        charsets: Dict[str, Charset] = {}
        for name, spec in (data.get("charsets") or {}).items():
            if name.startswith("_"):
                continue
            if isinstance(spec, (str, list)):
                spec = {"flaps": spec}
            kwargs = {}
            if "fallback" in spec:
                kwargs["fallback"] = spec["fallback"]
            charsets[name] = Charset(name, spec["flaps"], spec.get("aliases"), **kwargs)
        if "default" not in charsets:
            charsets["default"] = Charset("default", LEGACY_40_FLAPS)

        raw_positions = data.get("positions")
        if not isinstance(raw_positions, list):
            raise ValueError("the config needs a 'positions' list (one entry per display position, left to right)")
        positions = []
        for i, entry in enumerate(raw_positions):
            if isinstance(entry, int):
                entry = {"channel": entry}
            charset_name = entry.get("charset", "default")
            if charset_name not in charsets:
                raise ValueError(f"position {i}: unknown charset {charset_name!r}")
            positions.append(PositionConfig(int(entry["channel"]), charsets[charset_name]))

        rehome = data.get("auto_rehome", {})
        if isinstance(rehome, bool):
            rehome = {"enabled": rehome}
        return cls(
            positions=positions,
            port=data.get("port"),
            auto_rehome=bool(rehome.get("enabled", True)),
            max_rehome_attempts=int(rehome.get("max_attempts", 3)),
            rehome_window_s=float(rehome.get("window_s", 600.0)),
            rehome_backoff_s=float(rehome.get("backoff_s", 15.0)),
        )

    @classmethod
    def load(cls, path: str) -> "DisplayConfig":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ---------------------------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ModuleStatus:
    channel: int
    position: Optional[int]       # None = channel not used by the config
    state: ModuleState
    flap_index: int
    token: Optional[str]          # flap at flap_index in this position's charset
    moving: bool
    home_sensor: bool             # hall sensor currently sees the magnet
    missed_home: int              # times home was expected but not seen (module re-homes itself)
    unexpected_home: int          # times home was seen where it shouldn't be

    @property
    def symbol(self) -> str:
        if self.state is ModuleState.NORMAL:
            if self.token is None:
                return "?"
            return self.token if len(self.token) == 1 else "{" + self.token + "}"
        return {
            ModuleState.LOOK_FOR_HOME: "~",
            ModuleState.SENSOR_ERROR: "!",
            ModuleState.PANIC: "X",
            ModuleState.DISABLED: "-",
        }.get(self.state, "?")


@dataclass(frozen=True)
class DisplayStatus:
    connected: bool
    channels: Tuple[ModuleStatus, ...]     # every channel the firmware reports (NUM_MODULES)
    loopbacks_ok: Optional[bool]
    firmware: Optional[FirmwareInfo]
    received_at: Optional[float]           # time.time() of the last state report

    @property
    def positions(self) -> Tuple[ModuleStatus, ...]:
        """Configured modules, in display order."""
        used = [m for m in self.channels if m.position is not None]
        return tuple(sorted(used, key=lambda m: m.position))

    @property
    def text(self) -> str:
        """What the display shows. ~ homing, ! sensor error, X panic, - disabled."""
        return "".join(m.symbol for m in self.positions)

    @property
    def faults(self) -> List[str]:
        problems = []
        if not self.connected:
            problems.append("not connected")
        if self.loopbacks_ok is False:
            problems.append("Chainlink loopback check failing (ribbon cable / driver chain / NUM_MODULES); "
                            "the firmware disables every module")
        for m in self.positions:
            if m.state in (ModuleState.SENSOR_ERROR, ModuleState.PANIC, ModuleState.DISABLED, ModuleState.UNKNOWN):
                problems.append(f"position {m.position} (channel {m.channel}): {m.state.name}")
        return problems

    @property
    def healthy(self) -> bool:
        return not self.faults


# ---------------------------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------------------------

class _Kind(enum.Enum):
    CONFIG = 1
    COMMAND = 2
    REQUEST_STATE = 3


@dataclass(eq=False)
class _Outgoing:
    kind: _Kind
    body: bytes = b""                      # encoded SplitflapCommand for COMMAND messages
    done: threading.Event = field(default_factory=threading.Event)
    nonce: int = 0
    frame: bytes = b""
    attempts: int = 0
    next_send: float = 0.0


def list_ports():
    if serial is None:
        raise RuntimeError("pyserial is required: pip install pyserial")
    return sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)


def find_port() -> Optional[str]:
    """First serial port that looks like an ESP32 / T-Display USB bridge."""
    candidates = [p for p in list_ports() if (p.vid, p.pid) in KNOWN_USB_IDS]
    if len(candidates) > 1:
        log.warning("Several possible splitflap ports (%s); using %s. Set 'port' to choose.",
                    ", ".join(p.device for p in candidates), candidates[0].device)
    return candidates[0].device if candidates else None


def _is_idle(m: ModuleStatus) -> bool:
    return not m.moving and m.state is not ModuleState.LOOK_FOR_HOME


class SplitflapDisplay:
    """Thread-safe connection to a Chainlink splitflap controller over USB serial."""

    def __init__(self, config: DisplayConfig, port: Optional[str] = None):
        if serial is None:
            raise RuntimeError("pyserial is required: pip install pyserial")
        self.config = config
        self._port_setting = port or config.port
        self._pos_by_channel = {p.channel: i for i, p in enumerate(config.positions)}

        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._ser_lock = threading.Lock()
        self._ser = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._rx = bytearray()
        self._last_warning = ""

        # Outgoing messages: one in flight at a time, retried until acknowledged.
        self._outq: Deque[_Outgoing] = collections.deque()
        self._inflight: Optional[_Outgoing] = None
        self._last_enqueued: Optional[_Outgoing] = None
        self._nonce = random.randint(1, 2 ** 31)

        # What we want each channel to do (sent as a full SplitflapConfig snapshot).
        self._targets: Dict[int, int] = {}
        self._movement_nonce: Dict[int, int] = {}
        self._reset_nonce: Dict[int, int] = {}
        self._config_active = False

        # What the firmware reports.
        self._connected = False
        self._have_state = False
        self._channels: Tuple[ModuleStatus, ...] = ()
        self._num_channels: Optional[int] = None
        self._loopbacks_ok: Optional[bool] = None
        self._firmware: Optional[FirmwareInfo] = None
        self._state_seq = 0
        self._state_time: Optional[float] = None
        self._last_frame_time = 0.0
        self._last_poke = 0.0
        self._flap_count_checked = False

        # Automatic re-home bookkeeping.
        self._rehome_times: Dict[int, Deque[float]] = collections.defaultdict(collections.deque)
        self._gave_up: set = set()

        self._listeners: List[Callable[[DisplayStatus], None]] = []
        self._log_listeners: List[Callable[[str], None]] = []

    # ---- lifecycle ---------------------------------------------------------------------------

    def open(self) -> "SplitflapDisplay":
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._io_loop, name="splitflap-io", daemon=True)
            self._thread.start()
        return self

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._close_port()

    def __enter__(self) -> "SplitflapDisplay":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def wait_connected(self, timeout: float = 10.0) -> bool:
        """Wait until the port is open and the firmware has reported its state."""
        with self._cond:
            return self._cond.wait_for(lambda: self._connected and self._have_state, timeout)

    def wait_firmware(self, timeout: float = 3.0) -> Optional[FirmwareInfo]:
        """Wait for the firmware's GeneralState (sent every 2 s)."""
        with self._cond:
            self._cond.wait_for(lambda: self._firmware is not None, timeout)
            return self._firmware

    # ---- writing -----------------------------------------------------------------------------

    @property
    def num_positions(self) -> int:
        return len(self.config.positions)

    def charset(self, position: int) -> Charset:
        return self.config.positions[self._check_position(position)].charset

    def show_text(self, text: str, align: str = "left", force_rotation: bool = False) -> List[str]:
        """Show text. Use {NAME} for multi-character flaps. Returns tokens that weren't on the flaps."""
        return self.show(parse_tokens(text), align=align, force_rotation=force_rotation)

    def show(self, tokens: Sequence[Optional[str]], align: str = "left", force_rotation: bool = False) -> List[str]:
        """Show one token per position (None = leave that position alone).

        Shorter input is padded with blanks according to `align` ("left", "right" or "center").
        Tokens a module doesn't have use that charset's fallback flap, or leave the module alone.
        force_rotation makes modules that already show the right flap do a full turn anyway.
        Returns the tokens that weren't found.
        """
        n = self.num_positions
        items: List[Tuple[Optional[str], bool]] = [(t, False) for t in tokens]
        if len(items) > n:
            log.warning("%d flaps of text but only %d positions; cutting it short", len(items), n)
            items = items[:n]
        pad = n - len(items)
        blank = (" ", True)
        if align == "left":
            items = items + [blank] * pad
        elif align == "right":
            items = [blank] * pad + items
        elif align == "center":
            left = pad // 2
            items = [blank] * left + items + [blank] * (pad - left)
        else:
            raise ValueError(f"align must be left, right or center (got {align!r})")

        indexes: List[Optional[int]] = []
        missing: List[str] = []
        for pos, (token, is_padding) in enumerate(items):
            if token is None:
                indexes.append(None)
                continue
            charset = self.config.positions[pos].charset
            index = charset.lookup(token)
            if index is None:
                if not is_padding:
                    missing.append(token)
                index = charset.resolve(token)
            indexes.append(index)
        if missing:
            log.warning("Not on the flaps: %s", ", ".join(repr(t) for t in missing))
        self.show_indexes(indexes, force_rotation=force_rotation)
        return missing

    def show_indexes(self, indexes: Sequence[Optional[int]], force_rotation: bool = False) -> None:
        """Lowest level: a flap index per position (None = leave alone)."""
        if len(indexes) > self.num_positions:
            raise ValueError(f"{len(indexes)} indexes but only {self.num_positions} positions")
        with self._lock:
            for pos, index in enumerate(indexes):
                if index is None:
                    continue
                p = self.config.positions[pos]
                if not 0 <= index < len(p.charset):
                    raise ValueError(f"position {pos}: flap index {index} out of range 0..{len(p.charset) - 1}")
                self._targets[p.channel] = index
                if force_rotation:
                    self._movement_nonce[p.channel] = (self._movement_nonce.get(p.channel, 0) + 1) % 256
            self._enqueue_config_locked()

    def go_to_index(self, position: int, index: int, force_rotation: bool = False) -> None:
        indexes: List[Optional[int]] = [None] * self.num_positions
        indexes[self._check_position(position)] = index
        self.show_indexes(indexes, force_rotation=force_rotation)

    def rehome(self, positions: Optional[Iterable[int]] = None) -> None:
        """Clear error counters and look for home again (all configured positions by default)."""
        with self._lock:
            for ch in self._channels_for(positions):
                self._reset_nonce[ch] = (self._reset_nonce.get(ch, 0) + 1) % 256
                self._gave_up.discard(ch)
                self._rehome_times[ch].clear()
            self._enqueue_config_locked()

    def hard_reset(self) -> None:
        """Reset the ESP32 through the USB bridge's RTS/DTR lines (same sequence as Scott's library)."""
        with self._ser_lock:
            ser = self._ser
            if ser is None:
                raise RuntimeError("not connected")
            ser.rts = True
            ser.dtr = False
            time.sleep(0.2)
            ser.dtr = True
            time.sleep(0.2)
        log.info("Reset the ESP32; every module will re-home")

    # ---- calibration primitives (see `calibrate` in the CLI for the full procedure) -----------

    def nudge_offset(self, position: int, half: bool = False) -> threading.Event:
        """Move a module's home offset forward by 1/10 (or 1/2) of a flap. Not saved until save_calibration()."""
        action = _Action.INCREASE_OFFSET_HALF if half else _Action.INCREASE_OFFSET_TENTH
        return self._enqueue_module_command(self._channel(position), action)

    def set_offset_here(self, position: int) -> threading.Event:
        """Make the module's current position flap index 0. The firmware then does one full turn."""
        ch = self._channel(position)
        event = self._enqueue_module_command(ch, _Action.SET_OFFSET)
        with self._lock:
            self._targets[ch] = 0      # the firmware resets this module's target to flap 0
        return event

    def save_calibration(self) -> threading.Event:
        """Write every module's offset to the ESP32's flash. All modules must be idle.
        The firmware answers with a log line: 'SUCCESS - saved calibration!' or an error."""
        return self._enqueue(_Outgoing(_Kind.COMMAND, _encode_command([], save_all_offsets=True)))

    # ---- reading -----------------------------------------------------------------------------

    def status(self) -> DisplayStatus:
        with self._lock:
            return DisplayStatus(self._connected, self._channels, self._loopbacks_ok, self._firmware, self._state_time)

    def status_of(self, position: int) -> Optional[ModuleStatus]:
        ch = self._channel(position)
        with self._lock:
            return self._channels[ch] if ch < len(self._channels) else None

    def flap_count_problems(self) -> List[str]:
        """Charsets whose length doesn't match the firmware's NUM_FLAPS."""
        with self._lock:
            fw = self._firmware
        if fw is None or fw.num_flaps == 0:
            return []
        bad = sorted({(p.charset.name, len(p.charset)) for p in self.config.positions if len(p.charset) != fw.num_flaps})
        return [f"charset '{name}' has {count} flaps but the firmware was built with NUM_FLAPS={fw.num_flaps} "
                f"(firmware/src/config.h)" for name, count in bad]

    def wait_until_idle(self, positions: Optional[Iterable[int]] = None, timeout: float = 60.0) -> bool:
        """Block until everything queued so far has been delivered and the modules have stopped
        moving / homing. Returns False on timeout. Check status() afterwards for errors."""
        deadline = time.monotonic() + timeout
        with self._lock:
            channels = self._channels_for(positions)
            last = self._last_enqueued
        if last is not None and not last.done.wait(max(0.0, deadline - time.monotonic())):
            return False
        time.sleep(0.15)   # let the firmware act on what we sent before asking for fresh state
        while True:
            with self._cond:
                seq = self._state_seq
            self._enqueue(_Outgoing(_Kind.REQUEST_STATE))
            with self._cond:
                self._cond.wait_for(lambda: self._state_seq > seq,
                                    max(0.0, min(1.5, deadline - time.monotonic())))
                mods = self._channels
            if mods and all(_is_idle(mods[ch]) for ch in channels if ch < len(mods)):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.2)

    def add_listener(self, callback: Callable[[DisplayStatus], None]) -> Callable[[], None]:
        """callback(status) on every state report and on connect/disconnect. Returns an unsubscribe function."""
        with self._lock:
            self._listeners.append(callback)

        def remove() -> None:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)
        return remove

    def add_log_listener(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """callback(message) for every log line from the firmware. Returns an unsubscribe function."""
        with self._lock:
            self._log_listeners.append(callback)

        def remove() -> None:
            with self._lock:
                if callback in self._log_listeners:
                    self._log_listeners.remove(callback)
        return remove

    # ---- internals: helpers ------------------------------------------------------------------

    def _check_position(self, position: int) -> int:
        if not 0 <= position < self.num_positions:
            raise ValueError(f"position {position} out of range 0..{self.num_positions - 1}")
        return position

    def _channel(self, position: int) -> int:
        return self.config.positions[self._check_position(position)].channel

    def _channels_for(self, positions: Optional[Iterable[int]]) -> List[int]:
        if positions is None:
            return [p.channel for p in self.config.positions]
        return [self._channel(pos) for pos in positions]

    def _enqueue(self, msg: _Outgoing) -> threading.Event:
        with self._lock:
            tail = self._outq[-1] if self._outq else None
            if tail is not None and tail.kind is msg.kind and msg.kind in (_Kind.CONFIG, _Kind.REQUEST_STATE):
                return tail.done   # a config is a full snapshot built at send time, so one queued copy is enough
            self._outq.append(msg)
            self._last_enqueued = msg
            if len(self._outq) > 20:
                log.warning("%d messages waiting to be sent; is the splitflap still connected?", len(self._outq))
            return msg.done

    def _enqueue_config_locked(self) -> threading.Event:
        self._config_active = True
        return self._enqueue(_Outgoing(_Kind.CONFIG))

    def _enqueue_module_command(self, channel: int, action: _Action, param: int = 0) -> threading.Event:
        actions = [(_Action.NO_OP, 0)] * channel + [(action, param)]
        return self._enqueue(_Outgoing(_Kind.COMMAND, _encode_command(actions)))

    def _take_nonce(self) -> int:
        # The firmware ignores a message whose nonce equals the last one it handled (and starts at 0).
        self._nonce = ((self._nonce + 1) & 0xFFFFFFFF) or 1
        return self._nonce

    def _build_frame_locked(self, msg: _Outgoing) -> bytes:
        if msg.kind is _Kind.CONFIG:
            # Always send every channel: channels missing from a SplitflapConfig are treated as target 0.
            modules = [(self._targets.get(ch, 0), self._movement_nonce.get(ch, 0), self._reset_nonce.get(ch, 0))
                       for ch in range(self._num_channels or 0)]
            body = _pb_msg(3, _encode_config(modules))
        elif msg.kind is _Kind.COMMAND:
            body = _pb_msg(2, msg.body)
        else:
            body = _pb_msg(4, b"")
        payload = _pb_uint(1, msg.nonce) + body
        return cobs_encode(payload + struct.pack("<I", zlib.crc32(payload) & 0xFFFFFFFF))

    def _warn_once(self, message: str) -> None:
        if message != self._last_warning:
            self._last_warning = message
            log.warning(message)

    def _notify_listeners(self) -> None:
        status = self.status()
        with self._lock:
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(status)
            except Exception:
                log.exception("Status listener raised")

    # ---- internals: I/O thread ---------------------------------------------------------------

    def _io_loop(self) -> None:
        while not self._stop.is_set():
            if self._ser is None:
                if not self._open_port():
                    self._stop.wait(2.0)
                    continue
            try:
                ser = self._ser
                if ser is None:
                    continue
                waiting = ser.in_waiting
                data = ser.read(waiting or 1)      # returns after 50 ms if nothing arrives
                if data:
                    self._feed(data)
                self._service_tx()
                self._watchdog()
            except (serial.SerialException, OSError) as e:
                log.warning("Serial connection lost: %s", e)
                self._close_port()
                self._stop.wait(1.0)
            except Exception:
                log.exception("Unexpected error in the splitflap I/O thread")
                self._stop.wait(0.5)

    def _open_port(self) -> bool:
        try:
            port = self._port_setting or find_port()
        except Exception as e:
            self._warn_once(f"Couldn't list serial ports: {e}")
            return False
        if port is None:
            self._warn_once("No splitflap USB serial device found (plug it in, or set 'port' in the config / --port)")
            return False
        try:
            ser = serial.Serial(port, BAUD, timeout=0.05, write_timeout=1.0)
        except (serial.SerialException, OSError) as e:
            self._warn_once(f"Can't open {port}: {e}")
            return False
        self._last_warning = ""
        with self._ser_lock:
            self._ser = ser
        log.info("Opened %s", port)
        with self._cond:
            self._connected = True
            self._have_state = False
            self._rx.clear()
            self._last_frame_time = time.monotonic()
            if self._inflight is not None:
                self._inflight.next_send = 0.0
            self._outq.appendleft(_Outgoing(_Kind.REQUEST_STATE))
            if self._config_active:
                self._enqueue_config_locked()
            self._cond.notify_all()
        self._notify_listeners()
        return True

    def _close_port(self) -> None:
        with self._ser_lock:
            ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        with self._cond:
            was_connected = self._connected
            self._connected = False
            self._cond.notify_all()
        if was_connected:
            self._notify_listeners()

    def _service_tx(self) -> None:
        now = time.monotonic()
        with self._lock:
            msg = self._inflight
            if msg is None:
                if not self._outq:
                    return
                head = self._outq[0]
                if head.kind is _Kind.CONFIG and self._num_channels is None:
                    return   # need the channel count from the first state report
                self._outq.popleft()
                head.nonce = self._take_nonce()
                head.frame = self._build_frame_locked(head)
                self._inflight = msg = head
            if now < msg.next_send:
                return
            msg.attempts += 1
            msg.next_send = now + RETRY_INTERVAL_S
            frame = msg.frame
            attempts = msg.attempts
        if attempts == 20 or (attempts > 0 and attempts % 240 == 0):
            log.warning("No acknowledgement from the splitflap after %d tries. Is it powered, running the "
                        "Chainlink firmware, and not open in another program?", attempts)
        with self._ser_lock:
            if self._ser is None:
                return
            # The firmware boots in its legacy text protocol and switches to protobuf when it sees a
            # 0x00 byte. A leading 0x00 means a frame is never parsed as legacy commands (some of
            # which change offsets). In protobuf mode it's just an empty packet, which is ignored.
            self._ser.write(b"\x00" + frame + b"\x00")

    def _watchdog(self) -> None:
        # In protobuf mode the firmware sends GeneralState every 2 s. Silence means it rebooted
        # (and is back in legacy mode) or is busy: poke it with a state request.
        now = time.monotonic()
        if now - self._last_frame_time > SILENCE_POKE_S and now - self._last_poke > SILENCE_POKE_S:
            self._last_poke = now
            with self._lock:
                if self._inflight is None and not self._outq:
                    self._enqueue(_Outgoing(_Kind.REQUEST_STATE))

    def _feed(self, data: bytes) -> None:
        self._rx += data
        while True:
            i = self._rx.find(b"\x00")
            if i < 0:
                break
            frame = bytes(self._rx[:i])
            del self._rx[:i + 1]
            if frame:
                try:
                    self._handle_frame(frame)
                except Exception:
                    log.exception("Couldn't handle a message from the splitflap")
        if len(self._rx) > 8192:   # legacy-mode text with no frame delimiter
            self._rx.clear()

    def _handle_frame(self, frame: bytes) -> None:
        try:
            decoded = cobs_decode(frame)
        except ValueError:
            log.debug("Dropped a frame that isn't valid COBS (%d bytes)", len(frame))
            return
        if len(decoded) <= 4:
            return
        payload, (crc,) = decoded[:-4], struct.unpack("<I", decoded[-4:])
        if zlib.crc32(payload) & 0xFFFFFFFF != crc:
            log.debug("Dropped a frame with a bad CRC")
            return
        self._last_frame_time = time.monotonic()
        kind, value = _decode_from_splitflap(payload)
        if kind == "ack":
            self._on_ack(value)
        elif kind == "state":
            self._on_state(*value)
        elif kind == "general":
            self._on_general(value)
        elif kind == "log":
            self._on_log(value)

    def _on_ack(self, nonce: int) -> None:
        with self._lock:
            msg = self._inflight
            if msg is not None and msg.nonce == nonce:
                self._inflight = None
                msg.done.set()

    def _on_state(self, raw_modules: List[_RawModule], loopbacks_ok: bool) -> None:
        now = time.monotonic()
        with self._cond:
            previous = self._channels
            modules = []
            for ch, raw in enumerate(raw_modules):
                pos = self._pos_by_channel.get(ch)
                token = self.config.positions[pos].charset.token(raw.flap_index) if pos is not None else None
                modules.append(ModuleStatus(
                    channel=ch,
                    position=pos,
                    state=_to_module_state(raw.state),
                    flap_index=raw.flap_index,
                    token=token,
                    moving=raw.moving,
                    home_sensor=raw.home_state,
                    missed_home=raw.count_missed_home,
                    unexpected_home=raw.count_unexpected_home,
                ))
            if self._num_channels != len(modules):
                self._on_channel_count_locked(len(modules))
            if self._loopbacks_ok is not False and loopbacks_ok is False:
                log.error("Chainlink loopback check failed: the firmware has disabled every module. "
                          "Check the ribbon cables between the Buddy and the drivers, and NUM_MODULES.")
            self._channels = tuple(modules)
            self._loopbacks_ok = loopbacks_ok
            self._state_seq += 1
            self._state_time = time.time()
            first = not self._have_state
            self._have_state = True

            rehome = []
            for m in modules:
                if m.position is None:
                    continue
                old = previous[m.channel].state if m.channel < len(previous) else None
                if old is not m.state and not first:
                    level = logging.WARNING if m.state in (ModuleState.SENSOR_ERROR, ModuleState.PANIC,
                                                           ModuleState.DISABLED) else logging.INFO
                    log.log(level, "Position %d (channel %d): %s -> %s", m.position, m.channel,
                            old.name if old is not None else "?", m.state.name)
                if m.state is ModuleState.NORMAL:
                    self._gave_up.discard(m.channel)
                elif m.state is ModuleState.SENSOR_ERROR and self.config.auto_rehome:
                    if self._should_rehome_locked(m, now):
                        rehome.append(m.channel)
            if rehome:
                for ch in rehome:
                    self._reset_nonce[ch] = (self._reset_nonce.get(ch, 0) + 1) % 256
                self._enqueue_config_locked()
            self._cond.notify_all()
        self._notify_listeners()

    def _on_channel_count_locked(self, count: int) -> None:
        if self._num_channels is not None:
            log.warning("The firmware now reports %d channels (was %d)", count, self._num_channels)
        else:
            log.info("Firmware reports %d channels (NUM_MODULES)", count)
        self._num_channels = count
        for i, p in enumerate(self.config.positions):
            if p.channel >= count:
                log.error("Position %d uses channel %d, but the firmware only has channels 0..%d", i, p.channel, count - 1)

    def _should_rehome_locked(self, m: ModuleStatus, now: float) -> bool:
        times = self._rehome_times[m.channel]
        while times and now - times[0] > self.config.rehome_window_s:
            times.popleft()
        if times and now - times[-1] < self.config.rehome_backoff_s:
            return False
        if len(times) >= self.config.max_rehome_attempts:
            if m.channel not in self._gave_up:
                self._gave_up.add(m.channel)
                log.error("Position %d (channel %d) is still in SENSOR_ERROR after %d automatic re-homes; "
                          "leaving it alone. Check for a jammed flap or the sensor/magnet, then call rehome().",
                          m.position, m.channel, len(times))
            return False
        times.append(now)
        self._gave_up.discard(m.channel)
        log.warning("Position %d (channel %d) couldn't find home; re-homing (attempt %d of %d)",
                    m.position, m.channel, len(times), self.config.max_rehome_attempts)
        return True

    def _on_general(self, info: FirmwareInfo) -> None:
        with self._cond:
            previous = self._firmware
            self._firmware = info
            if previous is not None and info.uptime_ms + 1000 < previous.uptime_ms:
                log.warning("The splitflap controller restarted")
                if self._config_active:
                    self._enqueue_config_locked()
            check = not self._flap_count_checked
            self._flap_count_checked = True
            self._cond.notify_all()
        if check:
            for problem in self.flap_count_problems():
                log.error(problem)

    def _on_log(self, message: str) -> None:
        if message == "Small packet" or message.startswith("Already handled nonce"):
            device_log.debug(message)   # side effects of the leading 0x00 / retries
        else:
            device_log.info(message)
        with self._lock:
            listeners = list(self._log_listeners)
        for callback in listeners:
            try:
                callback(message)
            except Exception:
                log.exception("Log listener raised")


# ---------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------

def _load_config(path: Optional[str], required: bool = True) -> DisplayConfig:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [path] if path else ["splitflap_config.json", os.path.join(here, "splitflap_config.json")]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return DisplayConfig.load(candidate)
    if path:
        raise SystemExit(f"Config file not found: {path}")
    if required:
        raise SystemExit("No splitflap_config.json found. Copy splitflap_config.example.json to "
                         "splitflap_config.json and edit it, or pass --config.")
    return DisplayConfig(positions=[])


def _open_display(args, config_required: bool = True) -> SplitflapDisplay:
    config = _load_config(args.config, config_required)
    if config_required and not config.positions:
        raise SystemExit("The config has no positions.")
    display = SplitflapDisplay(config, port=args.port).open()
    if not display.wait_connected(timeout=10.0):
        display.close()
        raise SystemExit("Couldn't talk to the splitflap. Check the USB cable/port, close anything else using the "
                         "port (web app, PlatformIO serial monitor), and make sure the Chainlink firmware is flashed.")
    return display


def _require_matching_flaps(display: SplitflapDisplay) -> None:
    display.wait_firmware(3.0)
    problems = display.flap_count_problems()
    if problems:
        for problem in problems:
            print("ERROR:", problem)
        raise SystemExit("Fix NUM_FLAPS / the charsets first; letters can't line up until they match.")


def _format_uptime(ms: int) -> str:
    seconds = ms // 1000
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def format_status(status: DisplayStatus) -> str:
    lines = []
    fw = status.firmware
    if fw is not None:
        lines.append(f"Firmware {fw.git_hash or '?'} ({fw.build_date or '?'}), protocol v{fw.protocol_version}, "
                     f"NUM_FLAPS={fw.num_flaps or '?'}, up {_format_uptime(fw.uptime_ms)}")
    if status.loopbacks_ok is not None:
        lines.append("Loopbacks: " + ("OK" if status.loopbacks_ok else "FAILING"))
    lines.append(f"Showing: [{status.text}]")
    lines.append(f"{'Pos':>3} {'Ch':>3}  {'State':<13} {'Flap':>4}  {'Token':<8} {'Moving':<6} {'Sensor':<6} "
                 f"{'Missed':>6} {'Unexp':>6}")
    for m in status.positions:
        lines.append(f"{m.position:>3} {m.channel:>3}  {m.state.name:<13} {m.flap_index:>4}  "
                     f"{_token_label(m.token):<8} {'yes' if m.moving else 'no':<6} "
                     f"{'magnet' if m.home_sensor else '-':<6} {m.missed_home:>6} {m.unexpected_home:>6}")
    unused = [str(m.channel) for m in status.channels if m.position is None]
    if unused:
        lines.append("Unused channels: " + " ".join(unused))
    for fault in status.faults:
        lines.append("! " + fault)
    return "\n".join(lines)


def cmd_ports(args) -> int:
    ports = list_ports()
    if not ports:
        print("No serial ports found.")
    for p in ports:
        ids = f"{p.vid:04x}:{p.pid:04x}" if p.vid is not None else "----:----"
        mark = "  <- looks like an ESP32/T-Display" if (p.vid, p.pid) in KNOWN_USB_IDS else ""
        print(f"{p.device:<20} {ids}  {p.description}{mark}")
    return 0


def cmd_status(args) -> int:
    display = _open_display(args, config_required=False)
    try:
        display.wait_firmware(3.0)
        print(format_status(display.status()))
        if not args.watch:
            return 0
        print("\nWatching for changes (Ctrl+C to stop)...")
        last_key = [None]

        def on_status(st: DisplayStatus) -> None:
            key = (st.connected, st.loopbacks_ok, st.channels)
            if key != last_key[0]:
                last_key[0] = key
                print("\n" + time.strftime("%H:%M:%S") + "\n" + format_status(st))
        display.add_listener(on_status)
        while True:
            time.sleep(1.0)
    finally:
        display.close()


def _show_and_report(display: SplitflapDisplay, text: str, align: str, force: bool, wait: bool) -> None:
    missing = display.show_text(text, align=align, force_rotation=force)
    if missing:
        print("Not on the flaps (fallback used or module left alone):", ", ".join(repr(t) for t in missing))
    if wait:
        if not display.wait_until_idle(timeout=60.0):
            print("Timed out waiting for the modules to stop.")
        status = display.status()
        print(f"Showing: [{status.text}]")
        for fault in status.faults:
            print("! " + fault)


def cmd_show(args) -> int:
    display = _open_display(args)
    try:
        _require_matching_flaps(display)
        _show_and_report(display, args.text, args.align, args.force, wait=not args.no_wait)
        return 0
    finally:
        display.close()


def cmd_type(args) -> int:
    display = _open_display(args)
    try:
        _require_matching_flaps(display)
        print(f"{display.num_positions} positions. Type a line and press Enter ({{NAME}} for logo flaps). "
              "Ctrl+D or Ctrl+C to quit.")
        while True:
            try:
                line = input("> ")
            except EOFError:
                return 0
            try:
                _show_and_report(display, line, args.align, args.force, wait=True)
            except ValueError as e:
                print("Error:", e)
    finally:
        display.close()


def cmd_rehome(args) -> int:
    display = _open_display(args)
    try:
        display.rehome(args.positions or None)
        display.wait_until_idle(args.positions or None, timeout=60.0)
        print(format_status(display.status()))
        return 0 if display.status().healthy else 1
    finally:
        display.close()


def cmd_reset(args) -> int:
    display = _open_display(args, config_required=False)
    try:
        display.hard_reset()
        time.sleep(3.0)
        display.wait_until_idle(timeout=60.0)
        print(format_status(display.status()))
        return 0
    finally:
        display.close()


def cmd_cycle(args) -> int:
    display = _open_display(args)
    try:
        _require_matching_flaps(display)
        n = max(len(p.charset) for p in display.config.positions)
        print("Stepping every module through every flap. Check that each module shows the flap printed "
              "for it. Ctrl+C to stop.")
        for k in range(n):
            indexes = [k if k < len(p.charset) else None for p in display.config.positions]
            display.show_indexes(indexes)
            display.wait_until_idle(timeout=30.0)
            expected = " ".join(_token_label(p.charset.token(k)) for p in display.config.positions)
            print(f"flap {k:>2}: {expected}")
            time.sleep(args.delay)
        display.show_indexes([0] * display.num_positions)
        display.wait_until_idle(timeout=30.0)
        return 0
    finally:
        display.close()


def _ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        raise KeyboardInterrupt


def _calibrate_position(display: SplitflapDisplay, pos: int) -> bool:
    charset = display.charset(pos)
    n = len(charset)
    home = _token_label(charset.flaps[0])
    print(f"\n=== Position {pos} (channel {display.config.positions[pos].channel}), home flap = {home} ===")

    m = display.status_of(pos)
    if m is None or m.state is not ModuleState.NORMAL:
        print("This module isn't in NORMAL state; re-homing it first...")
        display.rehome([pos])
        display.wait_until_idle([pos], timeout=30.0)
        m = display.status_of(pos)
        if m is None or m.state is not ModuleState.NORMAL:
            print(f"It's still {m.state.name if m else 'missing'}: it can't find home. Fix the jam or the "
                  "sensor/magnet first. Skipping.")
            return False

    while True:
        display.go_to_index(pos, 0)
        display.wait_until_idle([pos], timeout=30.0)

        print("Step 1: press Enter to turn 1/10 of a flap forward. The moment a flap falls, type f and Enter.")
        print("        (Went past? Keep pressing Enter until the next flap falls.)")
        while True:
            answer = _ask("  [Enter] = nudge, f = a flap just fell, s = skip this module > ").strip().lower()
            if answer == "s":
                return False
            if answer == "f":
                break
            display.nudge_offset(pos)
            display.wait_until_idle([pos], timeout=10.0)
        display.nudge_offset(pos, half=True)   # move to the middle of that flap
        display.wait_until_idle([pos], timeout=10.0)

        while True:
            raw = _ask("Step 2: which flap is showing now? Type it (logo flaps by name, 'blank' for the "
                       "blank flap) > ")
            token = " " if raw == " " or raw.strip().lower() in ("blank", "space") else raw.strip()
            index = charset.lookup(token) if token else None
            if index is not None:
                break
            print(f"  {token!r} isn't in charset '{charset.name}'. Its flaps are: "
                  + " ".join(_token_label(t) for t in charset.flaps))
        steps = (n - index) % n
        if steps:
            display.go_to_index(pos, steps)
            display.wait_until_idle([pos], timeout=30.0)

        if _ask(f"Step 3: is {home} showing cleanly now? [Y/n] ").strip().lower().startswith("n"):
            print("Starting this module again.")
            continue

        display.set_offset_here(pos)
        display.wait_until_idle([pos], timeout=30.0)
        print("Re-homing to check the new offset...")
        display.rehome([pos])
        display.wait_until_idle([pos], timeout=30.0)
        m = display.status_of(pos)
        if m is None or m.state is not ModuleState.NORMAL:
            print(f"Re-home ended in {m.state.name if m else 'unknown'} state; trying this module again.")
            continue
        if _ask(f"Step 4: after re-homing, is {home} showing cleanly? [Y/n] ").strip().lower().startswith("n"):
            print("Starting this module again.")
            continue
        return True


def cmd_calibrate(args) -> int:
    display = _open_display(args)
    try:
        _require_matching_flaps(display)
        positions = args.positions or list(range(display.num_positions))
        print("Calibrating positions " + ", ".join(map(str, positions)) + ". Offsets are only kept if they're "
              "saved at the end.")
        done = []
        for pos in positions:
            if _calibrate_position(display, pos):
                done.append(pos)
        if not done:
            print("Nothing calibrated; not saving.")
            return 1

        print("\nSaving calibration to the ESP32's flash...")
        display.wait_until_idle(timeout=60.0)   # the firmware refuses to save while anything moves
        result: List[str] = []
        finished = threading.Event()

        def on_log(message: str) -> None:
            if message.startswith(("SUCCESS - saved", "ERROR - failed to save", "Can't save offsets")):
                result.append(message)
                finished.set()
        remove = display.add_log_listener(on_log)
        display.save_calibration()
        finished.wait(10.0)
        remove()
        if result and result[0].startswith("SUCCESS"):
            print("Saved. Calibrated positions: " + ", ".join(map(str, done)))
            return 0
        print("Save failed: " + (result[0] if result else "no reply from the firmware") + ". Run calibrate again "
              "or save from the web app.")
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Unsaved offsets are lost when the ESP32 restarts.")
        return 130
    finally:
        display.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Control a Scott Bezek splitflap display (Chainlink firmware) "
                                                 "over USB serial.")
    parser.add_argument("--config", "-c", help="config JSON (default: ./splitflap_config.json)")
    parser.add_argument("--port", "-p", help="serial port (default: from config, else auto-detect)")
    parser.add_argument("--verbose", "-v", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ports", help="list serial ports")
    p.set_defaults(func=cmd_ports)

    p = sub.add_parser("status", help="show module states, sensor counters and firmware info")
    p.add_argument("--watch", "-w", action="store_true", help="keep printing changes")
    p.set_defaults(func=cmd_status)

    for name, func, help_text in (("show", cmd_show, "show text, e.g. \"{ACA}857\""),
                                  ("type", cmd_type, "type lines interactively")):
        p = sub.add_parser(name, help=help_text)
        if name == "show":
            p.add_argument("text")
            p.add_argument("--no-wait", action="store_true", help="don't wait for the modules to stop")
        p.add_argument("--align", choices=("left", "right", "center"), default="left")
        p.add_argument("--force", action="store_true", help="full turn even for modules already showing the flap")
        p.set_defaults(func=func)

    p = sub.add_parser("calibrate", help="calibrate home offsets interactively, then save them")
    p.add_argument("positions", nargs="*", type=int, help="positions to calibrate (default: all)")
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("cycle", help="step every module through every flap to check the charset order")
    p.add_argument("--delay", type=float, default=1.0, help="seconds to pause on each flap")
    p.set_defaults(func=cmd_cycle)

    p = sub.add_parser("rehome", help="clear errors and find home again")
    p.add_argument("positions", nargs="*", type=int, help="positions (default: all)")
    p.set_defaults(func=cmd_rehome)

    p = sub.add_parser("reset", help="hard-reset the ESP32")
    p.set_defaults(func=cmd_reset)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())