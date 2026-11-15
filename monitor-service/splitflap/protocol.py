"""
protocol.py - the wire format the Chainlink firmware speaks.

COBS framing, a CRC32 trailer and the handful of protobuf messages in Scott Bezek's
proto/splitflap.proto, hand-rolled so the service needs no protobuf runtime: the messages are
small and this is the whole of them.

Nothing here knows about serial ports or displays. Frames go in and out as bytes:

    frame = encode_config_frame(nonce, [(flap_index, movement_nonce, reset_nonce), ...])
    kind, value = decode_frame(frame)      # ("state", ([RawModule, ...], loopbacks_ok))

The firmware's own enums (Action, ModuleState) and everything it tells us — the raw messages
(RawModule, FirmwareInfo) and the snapshots built out of them (SplitFlapStatus,
SplitFlapModuleStatus) — live here too, because the firmware defines them rather than we do.
The driver fills in the two things the wire doesn't carry: which display position a channel is,
and which flap its index names on that position's spool.
"""

import enum
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Iterator, List, NamedTuple, Optional, Sequence, Tuple, Union

__all__ = [
    "Action",
    "FirmwareInfo",
    "ModuleState",
    "ProtocolError",
    "RawModule",
    "SplitFlapModuleStatus",
    "SplitFlapStatus",
    "cobs_decode",
    "cobs_encode",
    "decode_frame",
    "encode_command",
    "encode_command_frame",
    "encode_config",
    "encode_config_frame",
    "encode_state_request_frame",
    "to_module_state",
]


class ProtocolError(ValueError):
    """A frame that isn't one of ours, or that arrived damaged."""


# ---------------------------------------------------------------------------------------------
# COBS framing, CRC32 and the protobuf bits we need
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


class Action(enum.IntEnum):
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


def to_module_state(value: int) -> ModuleState:
    try:
        return ModuleState(value)
    except ValueError:
        return ModuleState.UNKNOWN


def encode_config(modules: Sequence[Tuple[int, int, int]]) -> bytes:
    """SplitflapConfig. One (target_flap_index, movement_nonce, reset_nonce) per channel."""
    body = bytearray()
    for target, movement_nonce, reset_nonce in modules:
        body += _pb_msg(1, _pb_uint(1, target) + _pb_uint(2, movement_nonce) + _pb_uint(3, reset_nonce))
    return bytes(body)


def encode_command(actions: Sequence[Tuple[Action, int]], save_all_offsets: bool = False) -> bytes:
    """SplitflapCommand. One (action, param) per channel, starting at channel 0."""
    body = bytearray()
    for action, param in actions:
        body += _pb_msg(2, _pb_uint(1, int(action)) + _pb_uint(2, param))
    if save_all_offsets:
        body += _pb_uint(3, 1)
    return bytes(body)


class RawModule(NamedTuple):
    state: int
    flap_index: int
    moving: bool
    home_state: bool
    count_unexpected_home: int
    count_missed_home: int


def _decode_module_state(buf: bytes) -> RawModule:
    values = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for field_no, wire_type, value in _pb_fields(buf):
        if wire_type == 0 and field_no in values:
            values[field_no] = value
    return RawModule(values[1], values[2], bool(values[3]), bool(values[4]), values[5], values[6])


def _decode_splitflap_state(buf: bytes) -> Tuple[List[RawModule], bool]:
    modules: List[RawModule] = []
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


def _decode_message(buf: bytes):
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
# Frames
# ---------------------------------------------------------------------------------------------
#
# Every frame is a ToSplitflap/FromSplitflap message: a nonce, one of the messages above, and a
# CRC32 of both, COBS-encoded. The firmware ignores a message whose nonce matches the last one
# it handled, so the caller is responsible for moving the nonce on.

# Field numbers in ToSplitflap (proto/splitflap.proto).
_FIELD_NONCE = 1
_FIELD_COMMAND = 2
_FIELD_CONFIG = 3
_FIELD_REQUEST_STATE = 4


def _encode_frame(nonce: int, field_no: int, body: bytes = b"") -> bytes:
    payload = _pb_uint(_FIELD_NONCE, nonce) + _pb_msg(field_no, body)
    return cobs_encode(payload + struct.pack("<I", zlib.crc32(payload) & 0xFFFFFFFF))


def encode_config_frame(nonce: int, modules: Sequence[Tuple[int, int, int]]) -> bytes:
    """A full SplitflapConfig: (flap index, movement nonce, reset nonce) for every channel."""
    return _encode_frame(nonce, _FIELD_CONFIG, encode_config(modules))


def encode_command_frame(nonce: int, body: bytes) -> bytes:
    """A SplitflapCommand already encoded by encode_command()."""
    return _encode_frame(nonce, _FIELD_COMMAND, body)


def encode_state_request_frame(nonce: int) -> bytes:
    """Asks for a state report now, rather than waiting for the next one."""
    return _encode_frame(nonce, _FIELD_REQUEST_STATE)


def decode_frame(frame: bytes) -> Tuple[str, Any]:
    """
    One COBS frame from the firmware, as ("ack" | "state" | "general" | "log" | ..., value).

    Raises ProtocolError for anything that isn't a message of ours: the firmware boots in a
    legacy text mode and a serial line picks up noise, so this happens in normal use and the
    caller is expected to drop the frame and carry on.
    """
    try:
        decoded = cobs_decode(frame)
    except ValueError:
        raise ProtocolError(f"not valid COBS ({len(frame)} bytes)")
    if len(decoded) <= 4:
        raise ProtocolError(f"too short to hold a message and its CRC ({len(decoded)} bytes)")

    payload, (crc,) = decoded[:-4], struct.unpack("<I", decoded[-4:])
    if zlib.crc32(payload) & 0xFFFFFFFF != crc:
        raise ProtocolError("bad CRC")
    return _decode_message(payload)


# ---------------------------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------------------------
#
# Snapshots, not state: SplitFlapDriver builds a new SplitFlapStatus every time the firmware
# reports in, and hands the same frozen object to everything watching. The questions worth
# asking of a display ("is it idle?", "what is it showing?", "what is wrong with it?") are
# answered here rather than by whoever happens to be holding one.

@dataclass(frozen=True)
class SplitFlapModuleStatus:
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
    def idle(self) -> bool:
        """Stopped: not turning, and not hunting for home."""
        return not self.moving and self.state is not ModuleState.LOOK_FOR_HOME

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
class SplitFlapStatus:
    connected: bool
    channels: Tuple[SplitFlapModuleStatus, ...]     # every channel the firmware reports (NUM_MODULES)
    loopbacks_ok: Optional[bool]
    firmware: Optional[FirmwareInfo]
    received_at: Optional[float]           # time.time() of the last state report

    @property
    def positions(self) -> Tuple[SplitFlapModuleStatus, ...]:
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
