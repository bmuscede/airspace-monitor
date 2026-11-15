import collections
from dataclasses import dataclass, field
import enum
import logging
import random
import threading
import time
from typing import Callable, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

from splitflap.config import SplitFlapCharset, SplitFlapConfig, parse_tokens
from splitflap.protocol import (
    Action,
    FirmwareInfo,
    ModuleState,
    ProtocolError,
    RawModule,
    SplitFlapModuleStatus,
    SplitFlapStatus,
    decode_frame,
    encode_command,
    encode_command_frame,
    encode_config_frame,
    encode_state_request_frame,
    to_module_state,
)
from utils.logs import GetLogger

# Under the AirspaceMonitor logger, so the driver's own warnings land in the service log and
# the dashboard's Logs view. splitflap/calibrate.py points the same tree at the console.
log = GetLogger("SplitFlap.Driver")
device_log = GetLogger("SplitFlap.Firmware")

# Default baud rate of the COM connection.
BAUD = 230400

# Same retry interval as Scott's Python/JS libraries.
RETRY_INTERVAL_S = 0.25

# The firmware sends GeneralState every 2 s; silence means it is in legacy mode or has rebooted.
SILENCE_POKE_S = 6.0

# USB serial bridges used by ESP32 boards.
KNOWN_USB_IDS = {
    (0x10C4, 0xEA60),  # Silicon Labs CP210x
    (0x1A86, 0x55D4),  # QinHeng CH9102
}

class _Kind(enum.Enum):
    CONFIG = 1           # A configuration message.
    COMMAND = 2          # A command to change flaps.
    REQUEST_STATE = 3    # Request positional state from the device.

@dataclass(eq=False)
class _Outgoing:
    kind: _Kind
    body: bytes = b""                      # encoded SplitflapCommand for COMMAND messages
    done: threading.Event = field(default_factory=threading.Event)
    nonce: int = 0
    frame: bytes = b""
    attempts: int = 0
    next_send: float = 0.0


class SplitFlapDriver:
    """
    Thread-safe connection to a Chainlink splitflap controller over USB serial.
    
    Handles messaging to the SplitFlap device configured.
    """

    def __init__(self, config: SplitFlapConfig, port: Optional[str] = None):
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
        self._channels: Tuple[SplitFlapModuleStatus, ...] = ()
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

        self._listeners: List[Callable[[SplitFlapStatus], None]] = []
        self._log_listeners: List[Callable[[str], None]] = []

    @staticmethod
    def listPorts():
        """Every serial port on this machine, in device order."""
        if serial is None:
            raise RuntimeError("pyserial is required: pip install pyserial")
        return sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)


    @staticmethod
    def findPorts() -> Optional[str]:
        """First serial port that looks like an ESP32 / T-Display USB bridge."""
        candidates = [p for p in SplitFlapDriver.listPorts() if (p.vid, p.pid) in KNOWN_USB_IDS]
        
        if len(candidates) > 1:
            log.warning("Several possible splitflap ports (%s); using %s. Set 'port' to choose.",
                    ", ".join(p.device for p in candidates), candidates[0].device)
        
        return candidates[0].device if candidates else None

    # ---- lifecycle ---------------------------------------------------------------------------

    def open(self) -> "SplitFlapDriver":
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

    def __enter__(self) -> "SplitFlapDriver":
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

    def charset(self, position: int) -> SplitFlapCharset:
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

    # ---- calibration primitives (splitflap/calibrate.py drives the full procedure) -----------

    def nudge_offset(self, position: int, half: bool = False) -> threading.Event:
        """Move a module's home offset forward by 1/10 (or 1/2) of a flap. Not saved until save_calibration()."""
        action = Action.INCREASE_OFFSET_HALF if half else Action.INCREASE_OFFSET_TENTH
        return self._enqueue_module_command(self._channel(position), action)

    def set_offset_here(self, position: int) -> threading.Event:
        """Make the module's current position flap index 0. The firmware then does one full turn."""
        ch = self._channel(position)
        event = self._enqueue_module_command(ch, Action.SET_OFFSET)
        with self._lock:
            self._targets[ch] = 0      # the firmware resets this module's target to flap 0
        return event

    def save_calibration(self) -> threading.Event:
        """Write every module's offset to the ESP32's flash. All modules must be idle.
        The firmware answers with a log line: 'SUCCESS - saved calibration!' or an error."""
        return self._enqueue(_Outgoing(_Kind.COMMAND, encode_command([], save_all_offsets=True)))

    # ---- reading -----------------------------------------------------------------------------

    def status(self) -> SplitFlapStatus:
        with self._lock:
            return SplitFlapStatus(self._connected, self._channels, self._loopbacks_ok, self._firmware, self._state_time)

    def status_of(self, position: int) -> Optional[SplitFlapModuleStatus]:
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
            if mods and all(mods[ch].idle for ch in channels if ch < len(mods)):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.2)

    def add_listener(self, callback: Callable[[SplitFlapStatus], None]) -> Callable[[], None]:
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

    def _enqueue_module_command(self, channel: int, action: Action, param: int = 0) -> threading.Event:
        actions = [(Action.NO_OP, 0)] * channel + [(action, param)]
        return self._enqueue(_Outgoing(_Kind.COMMAND, encode_command(actions)))

    def _take_nonce(self) -> int:
        # The firmware ignores a message whose nonce equals the last one it handled (and starts at 0).
        self._nonce = ((self._nonce + 1) & 0xFFFFFFFF) or 1
        return self._nonce

    def _build_frame_locked(self, msg: _Outgoing) -> bytes:
        if msg.kind is _Kind.CONFIG:
            # Always send every channel: channels missing from a SplitflapConfig are treated as target 0.
            modules = [(self._targets.get(ch, 0), self._movement_nonce.get(ch, 0), self._reset_nonce.get(ch, 0))
                       for ch in range(self._num_channels or 0)]
            return encode_config_frame(msg.nonce, modules)
        if msg.kind is _Kind.COMMAND:
            return encode_command_frame(msg.nonce, msg.body)
        return encode_state_request_frame(msg.nonce)

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
            port = self._port_setting or self.findPorts()
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
            kind, value = decode_frame(frame)
        except ProtocolError as e:
            # Normal in use: the firmware boots in a legacy text mode, and a serial line
            # picks up noise.
            log.debug("Dropped a frame from the splitflap: %s", e)
            return
        self._last_frame_time = time.monotonic()
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

    def _on_state(self, raw_modules: List[RawModule], loopbacks_ok: bool) -> None:
        now = time.monotonic()
        with self._cond:
            previous = self._channels
            modules = []
            for ch, raw in enumerate(raw_modules):
                pos = self._pos_by_channel.get(ch)
                token = self.config.positions[pos].charset.token(raw.flap_index) if pos is not None else None
                modules.append(SplitFlapModuleStatus(
                    channel=ch,
                    position=pos,
                    state=to_module_state(raw.state),
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

    def _should_rehome_locked(self, m: SplitFlapModuleStatus, now: float) -> bool:
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

