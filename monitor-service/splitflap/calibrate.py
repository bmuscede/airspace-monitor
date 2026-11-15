#!/usr/bin/env python3
"""
calibrate.py - set up and check the split-flap display by hand.

Everything about the split-flap that needs a person watching it lives here rather than in the
service: measuring each module's home offset, stepping every module through every flap to check
the charset matches the spool, and writing a line of text to see where it lands.

The display is described by the "splitflap" section of the service's config.json — the same
channels, charsets and port the service uses, so there is nothing to keep in step. Calibration
offsets are saved to the ESP32's flash; what config.json remembers is that they have been saved
(splitflap.calibration), which is what stops the service from redoing it on every boot.

    python -m splitflap.calibrate ports                 # list serial ports
    python -m splitflap.calibrate status [--watch]      # module states, sensor counters, firmware
    python -m splitflap.calibrate calibrate [POS ...]   # measure home offsets, then save them
    python -m splitflap.calibrate show "{ACA}857"       # write text; {NAME} is a logo flap
    python -m splitflap.calibrate cycle                 # step every module through every flap
    python -m splitflap.calibrate rehome [POS ...]      # clear errors and find home again
    python -m splitflap.calibrate reset                 # hard-reset the ESP32
    python -m splitflap.calibrate forget                # drop the saved calibration state

    Options: --config_dir DIR (default .), --port PORT, --verbose

Only one program can hold the serial port, so stop the service first:

    sudo systemctl stop airspace-monitor-service

scripts/calibrate-splitflap.sh does that for you, and starts it again afterwards.
"""

import argparse
import logging
import os
import sys
import threading
import time
from typing import List, Optional, Sequence

# The service's modules are rooted one directory up, next to main.py, however this file was
# invoked (python -m splitflap.calibrate, or by path from somewhere else).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from splitflap.config import SplitFlapConfig, parse_tokens, token_label
from splitflap.driver import KNOWN_USB_IDS, SplitFlapDriver
from splitflap.protocol import ModuleState, SplitFlapStatus
from utils.config import ConfigManager
from utils.logs import InitializeConsoleLogging

# The display is mechanical: a full turn plus the hunt for the magnet.
SETTLE_TIMEOUT_S = 60.0

# How long the firmware gets to answer a save with its log line.
SAVE_TIMEOUT_S = 10.0


# ---------------------------------------------------------------------------------------------
# Opening the display
# ---------------------------------------------------------------------------------------------

def open_driver(args, need_channels: bool = True) -> SplitFlapDriver:
    """
    Opens the display config.json describes.

    `ports`, `status` and `reset` work on a display with no channels configured yet, which is
    where a builder starts; everything that writes flaps needs them.
    """
    section = ConfigManager(args.config_dir).Get("splitflap") or {}
    if need_channels and not section.get("channels"):
        raise SystemExit(
            f"The splitflap section of {os.path.join(args.config_dir, 'config.json')} has no channels. "
            "Add one entry per flap (left to right, then row by row) with the Chainlink channel it is "
            "wired to and the charset on its spool, then run this again."
        )

    config = SplitFlapConfig.from_service_section(section)
    # The service heals a module that loses home by re-homing it in the background. In here
    # that is the wrong thing to do: the procedure parks a module away from home on purpose
    # and then asks the builder what they can see, so a re-home between the question and the
    # answer would measure the offset from the wrong flap. In this tool a module moves only
    # when it is told to, and a sticking one is reported instead.
    config.auto_rehome = False
    display = SplitFlapDriver(config, port=args.port).open()
    if not display.wait_connected(timeout=10.0):
        display.close()
        raise SystemExit(
            "Couldn't talk to the splitflap. Check the USB cable and the port, make sure the "
            "Chainlink firmware is flashed, and stop anything else holding the port:\n"
            "  sudo systemctl stop airspace-monitor-service"
        )
    return display


def require_matching_flaps(display: SplitFlapDriver) -> None:
    """Letters cannot line up while the charsets and the firmware disagree about NUM_FLAPS."""
    display.wait_firmware(3.0)
    problems = display.flap_count_problems()
    if problems:
        for problem in problems:
            print("ERROR:", problem)
        raise SystemExit("Fix NUM_FLAPS or the charsets first.")


# ---------------------------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------------------------

def format_uptime(ms: int) -> str:
    seconds = ms // 1000
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def format_status(status: SplitFlapStatus) -> str:
    lines = []
    fw = status.firmware
    if fw is not None:
        lines.append(f"Firmware {fw.git_hash or '?'} ({fw.build_date or '?'}), protocol v{fw.protocol_version}, "
                     f"NUM_FLAPS={fw.num_flaps or '?'}, up {format_uptime(fw.uptime_ms)}")
    if status.loopbacks_ok is not None:
        lines.append("Loopbacks: " + ("OK" if status.loopbacks_ok else "FAILING"))
    lines.append(f"Showing: [{status.text}]")
    lines.append(f"{'Pos':>3} {'Ch':>3}  {'State':<13} {'Flap':>4}  {'Token':<8} {'Moving':<6} {'Sensor':<6} "
                 f"{'Missed':>6} {'Unexp':>6}")
    for m in status.positions:
        lines.append(f"{m.position:>3} {m.channel:>3}  {m.state.name:<13} {m.flap_index:>4}  "
                     f"{token_label(m.token):<8} {'yes' if m.moving else 'no':<6} "
                     f"{'magnet' if m.home_sensor else '-':<6} {m.missed_home:>6} {m.unexpected_home:>6}")
    unused = [str(m.channel) for m in status.channels if m.position is None]
    if unused:
        lines.append("Unused channels: " + " ".join(unused))
    for fault in status.faults:
        lines.append("! " + fault)
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------
# Calibration state, as the service sees it
# ---------------------------------------------------------------------------------------------

def record_calibration(config_dir: str, calibrated: bool) -> None:
    """
    Writes the calibration state the service reads on startup.

    The offsets live in the ESP32's flash. This is only the note that says they are there, so
    the service homes and saves once rather than on every boot.
    """
    manager = ConfigManager(config_dir)
    manager.Set("splitflap.calibration.calibrated", calibrated)
    manager.Set("splitflap.calibration.calibrated_at", time.time() if calibrated else 0.0)
    manager.SaveConfig()


# ---------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------

def cmd_ports(args) -> int:
    ports = SplitFlapDriver.listPorts()
    if not ports:
        print("No serial ports found.")
    for p in ports:
        ids = f"{p.vid:04x}:{p.pid:04x}" if p.vid is not None else "----:----"
        mark = "  <- looks like an ESP32/T-Display" if (p.vid, p.pid) in KNOWN_USB_IDS else ""
        print(f"{p.device:<20} {ids}  {p.description}{mark}")
    return 0


def cmd_status(args) -> int:
    display = open_driver(args, need_channels=False)
    try:
        display.wait_firmware(3.0)
        print(format_status(display.status()))
        if not args.watch:
            return 0

        print("\nWatching for changes (Ctrl+C to stop)...")
        last_key = [None]

        def on_status(status: SplitFlapStatus) -> None:
            key = (status.connected, status.loopbacks_ok, status.channels)
            if key != last_key[0]:
                last_key[0] = key
                print("\n" + time.strftime("%H:%M:%S") + "\n" + format_status(status))

        display.add_listener(on_status)
        while True:
            time.sleep(1.0)
    finally:
        display.close()


def cmd_show(args) -> int:
    display = open_driver(args)
    try:
        require_matching_flaps(display)
        missing = display.show_text(args.text, align=args.align, force_rotation=args.force)
        if missing:
            print("Not on the flaps (fallback used, or the module was left alone):",
                  ", ".join(repr(t) for t in missing))
        if not display.wait_until_idle(timeout=SETTLE_TIMEOUT_S):
            print("Timed out waiting for the modules to stop.")
        status = display.status()
        print(f"Showing: [{status.text}]")
        for fault in status.faults:
            print("! " + fault)
        return 0
    finally:
        display.close()


def cmd_cycle(args) -> int:
    display = open_driver(args)
    try:
        require_matching_flaps(display)
        flaps = max(len(p.charset) for p in display.config.positions)
        print("Stepping every module through every flap. Check that each one shows the flap printed for "
              "it: a module that is off by one has its charset in the wrong order, or needs calibrating. "
              "Ctrl+C to stop.")
        for k in range(flaps):
            display.show_indexes([k if k < len(p.charset) else None for p in display.config.positions])
            display.wait_until_idle(timeout=30.0)
            print(f"flap {k:>2}: " + " ".join(token_label(p.charset.token(k)) for p in display.config.positions))
            time.sleep(args.delay)
        display.show_indexes([0] * display.num_positions)
        display.wait_until_idle(timeout=30.0)
        return 0
    finally:
        display.close()


def cmd_rehome(args) -> int:
    display = open_driver(args)
    try:
        positions = args.positions or None
        display.rehome(positions)
        display.wait_until_idle(positions, timeout=SETTLE_TIMEOUT_S)
        status = display.status()
        print(format_status(status))
        return 0 if status.healthy else 1
    finally:
        display.close()


def cmd_reset(args) -> int:
    display = open_driver(args, need_channels=False)
    try:
        display.hard_reset()
        time.sleep(3.0)
        display.wait_until_idle(timeout=SETTLE_TIMEOUT_S)
        print(format_status(display.status()))
        return 0
    finally:
        display.close()


def cmd_forget(args) -> int:
    """Makes the service calibrate again next time it starts."""
    record_calibration(args.config_dir, False)
    print("Forgot the saved calibration. The service will home every module and save the offsets "
          "again the next time it starts.")
    return 0


# ---------------------------------------------------------------------------------------------
# The interactive procedure
# ---------------------------------------------------------------------------------------------

def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        raise KeyboardInterrupt


def calibrate_position(display: SplitFlapDriver, pos: int) -> bool:
    """
    Walks one module through the procedure from Scott's web app.

    Nudge the spool a tenth of a flap at a time until a flap falls, say which flap is showing,
    and the module works out where home is from the difference. Returns False if it was skipped.
    """
    charset = display.charset(pos)
    flaps = len(charset)
    home = token_label(charset.flaps[0])
    logo = next((token_label(t) for t in charset.flaps if len(t) > 1), None)
    print(f"\n=== Position {pos} (channel {display.config.positions[pos].channel}), home flap = {home} ===")

    module = display.status_of(pos)
    if module is None or module.state is not ModuleState.NORMAL:
        print("This module isn't in NORMAL state; re-homing it first...")
        display.rehome([pos])
        display.wait_until_idle([pos], timeout=30.0)
        module = display.status_of(pos)
        if module is None or module.state is not ModuleState.NORMAL:
            print(f"It's still {module.state.name if module else 'missing'}: it can't find home. Fix the "
                  "jam or the sensor/magnet first. Skipping.")
            return False

    while True:
        display.go_to_index(pos, 0)
        display.wait_until_idle([pos], timeout=30.0)

        print("Step 1: press Enter to turn 1/10 of a flap forward. The moment a flap falls, type f and Enter.")
        print("        (Went past? Keep pressing Enter until the next flap falls.)")
        while True:
            answer = ask("  [Enter] = nudge, f = a flap just fell, s = skip this module > ").strip().lower()
            if answer == "s":
                return False
            if answer == "f":
                break
            display.nudge_offset(pos)
            display.wait_until_idle([pos], timeout=10.0)
        display.nudge_offset(pos, half=True)   # move to the middle of that flap
        display.wait_until_idle([pos], timeout=10.0)

        hint = f"{logo} for a logo flap, " if logo else ""
        while True:
            raw = ask(f"Step 2: which flap is showing now? Type it ({hint}'blank' for the "
                      "blank flap) > ")
            typed = raw.strip()
            if raw == " " or typed.lower() in ("blank", "space"):
                typed, tokens = "(blank)", [" "]
            elif not typed:
                continue
            else:
                try:
                    tokens = parse_tokens(typed)
                except ValueError as e:
                    print(f"  {e}")
                    continue
            if len(tokens) != 1:
                # Typing SWA for {SWA} is the easy mistake, and it reads as three flaps.
                print(f"  {typed!r} is {len(tokens)} flaps ("
                      + " ".join(token_label(t) for t in tokens)
                      + "). Only one flap is showing, so a flap whose name is longer than one "
                      "character is typed in braces, like " + (logo or "{ACA}") + ".")
                continue
            index = charset.lookup(tokens[0])
            if index is not None:
                break
            print(f"  {typed} isn't in charset '{charset.name}'. Its flaps are: "
                  + " ".join(token_label(t) for t in charset.flaps))
        steps = (flaps - index) % flaps
        if steps:
            display.go_to_index(pos, steps)
            display.wait_until_idle([pos], timeout=30.0)

        if ask(f"Step 3: is {home} showing cleanly now? [Y/n] ").strip().lower().startswith("n"):
            print("Starting this module again.")
            continue

        display.set_offset_here(pos)
        display.wait_until_idle([pos], timeout=30.0)
        print("Re-homing to check the new offset...")
        display.rehome([pos])
        display.wait_until_idle([pos], timeout=30.0)
        module = display.status_of(pos)
        if module is None or module.state is not ModuleState.NORMAL:
            print(f"Re-home ended in {module.state.name if module else 'unknown'} state; trying this module "
                  "again.")
            continue
        if ask(f"Step 4: after re-homing, is {home} showing cleanly? [Y/n] ").strip().lower().startswith("n"):
            print("Starting this module again.")
            continue
        return True


def save_offsets(display: SplitFlapDriver, timeout: float = SAVE_TIMEOUT_S) -> Optional[str]:
    """
    Writes every module's offset to the ESP32's flash. The firmware answers with a log line
    rather than an acknowledgement, so listen for it. Returns the reply, or None if it kept quiet.
    """
    replies: List[str] = []
    answered = threading.Event()

    def on_log(message: str) -> None:
        if message.startswith(("SUCCESS - saved", "ERROR - failed to save", "Can't save offsets")):
            replies.append(message)
            answered.set()

    remove = display.add_log_listener(on_log)
    try:
        display.save_calibration()
        answered.wait(timeout)
    finally:
        remove()
    return replies[0] if replies else None


def cmd_calibrate(args) -> int:
    display = open_driver(args)
    try:
        require_matching_flaps(display)
        positions = args.positions or list(range(display.num_positions))
        print("Calibrating positions " + ", ".join(map(str, positions))
              + ". Offsets are only kept if they are saved at the end.")

        done, skipped = [], []
        for pos in positions:
            (done if calibrate_position(display, pos) else skipped).append(pos)
        if skipped:
            print("\nSkipped " + ", ".join(f"position {pos} (channel "
                  f"{display.config.positions[pos].channel})" for pos in skipped)
                  + ": a module that can't find home can't be calibrated. Their saved offsets are "
                  "left as they are.")
        if not done:
            print("Nothing calibrated; not saving.")
            return 1

        print("\nSaving the offsets to the ESP32's flash...")
        display.wait_until_idle(timeout=SETTLE_TIMEOUT_S)   # the firmware refuses to save while anything moves
        reply = save_offsets(display)
        if reply is None or not reply.startswith("SUCCESS"):
            print("Save failed: " + (reply or "no reply from the firmware") + ". Run calibrate again.")
            return 1

        print("Saved. Calibrated positions: " + ", ".join(map(str, done)))
        if skipped:
            print("Still not calibrated: " + ", ".join(map(str, skipped))
                  + ". Fix the sensor or the jam, then run calibrate on just those positions.")
        record_calibration(args.config_dir, True)
        print("Recorded in config.json, so the service will leave the offsets alone from now on.")
        return 0
    except KeyboardInterrupt:
        print("\nStopped. Unsaved offsets are lost when the ESP32 restarts.")
        return 130
    finally:
        display.close()


# ---------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manual calibration program for the SplitFlap display. The service must be stopped first: "
                    "only one program can hold the serial port.")
    parser.add_argument("--config_dir", default=".", help="directory holding config.json (default: .)")
    parser.add_argument("--port", "-p", help="serial port (default: from config.json, else auto-detect)")
    parser.add_argument("--verbose", "-v", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ports", help="list serial ports")
    p.set_defaults(func=cmd_ports)

    p = sub.add_parser("status", help="show module states, sensor counters and firmware info")
    p.add_argument("--watch", "-w", action="store_true", help="keep printing changes")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("calibrate", help="measure home offsets interactively, then save them")
    p.add_argument("positions", nargs="*", type=int, help="positions to calibrate (default: all)")
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("show", help='write text, e.g. "{ACA}857"')
    p.add_argument("text")
    p.add_argument("--align", choices=("left", "right", "center"), default="left")
    p.add_argument("--force", action="store_true", help="full turn even for modules already showing the flap")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("cycle", help="step every module through every flap to check the charset order")
    p.add_argument("--delay", type=float, default=1.0, help="seconds to pause on each flap")
    p.set_defaults(func=cmd_cycle)

    p = sub.add_parser("rehome", help="clear errors and find home again")
    p.add_argument("positions", nargs="*", type=int, help="positions (default: all)")
    p.set_defaults(func=cmd_rehome)

    p = sub.add_parser("reset", help="hard-reset the ESP32")
    p.set_defaults(func=cmd_reset)

    p = sub.add_parser("forget", help="drop the saved calibration state so the service calibrates again")
    p.set_defaults(func=cmd_forget)

    args = parser.parse_args(argv)

    # The driver logs through the service's logger tree, so point that at the console.
    InitializeConsoleLogging(logging.DEBUG if args.verbose else logging.INFO)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        return 130

if __name__ == "__main__":
    sys.exit(main())
