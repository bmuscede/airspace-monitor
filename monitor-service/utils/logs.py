import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# The chatty log the dashboard's Logs view tails. Lives on tmpfs, so writing to
# it costs nothing on the SD card.
LOG_FILE_NAME = "system.log"

# WARNING and above only. Small, low-volume, and survives a reboot — this is
# what we actually need to diagnose a failure after the fact.
PERSISTENT_LOG_FILE_NAME = "system.error.log"

# A Pi Zero 2 W has 512MB of RAM. The live log is in that RAM, so it is sized
# for memory rather than disk: the old 50MB x 2 would have eaten nearly a third
# of the machine. /api/logs only ever reads the last 200 lines anyway.
LIVE_MAX_MB = 5
LIVE_BACKUP_COUNT = 2
PERSISTENT_MAX_MB = 2
PERSISTENT_BACKUP_COUNT = 2

# Must stay byte-identical: /api/logs parses this by splitting on spaces and
# the dashboard expects timestamp / level / source / message.
LOG_FORMAT = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

_live_log_path = None
_root_logger_name = "AirspaceMonitor"


def InitializeLogging(
    name="AirspaceMonitor",
    log_path="",
    live_log_path=None,
    level="INFO",
):
    """
    Sets up two handlers split by level and destination.

    1. Live handler -> `live_log_path` (tmpfs on the Pi). Everything at the
       configured level and above. This is what /api/logs tails.
    2. Persistent handler -> `log_path` (SD card). WARNING and above only.

    The high-volume chatter that used to dominate the write stream now never
    touches the card at all, and the entries worth keeping are written
    immediately rather than copied over on a timer.

    If `live_log_path` is unset or unusable we fall back to `log_path`, which is
    the normal case for a development machine.
    """
    global _live_log_path, _root_logger_name

    _root_logger_name = name
    level_value = _resolve_level(level)

    logger = logging.getLogger(name)
    logger.setLevel(level_value)

    # Avoid adding multiple handlers.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    live_directory = _usable_directory(live_log_path) or _usable_directory(log_path) or ""
    _live_log_path = os.path.join(live_directory, LOG_FILE_NAME)

    live_handler = RotatingFileHandler(
        _live_log_path,
        maxBytes=LIVE_MAX_MB * 1024 * 1024,
        backupCount=LIVE_BACKUP_COUNT,
    )
    live_handler.setLevel(level_value)
    live_handler.setFormatter(formatter)
    logger.addHandler(live_handler)

    persistent_directory = _usable_directory(log_path) or ""
    persistent_handler = RotatingFileHandler(
        os.path.join(persistent_directory, PERSISTENT_LOG_FILE_NAME),
        maxBytes=PERSISTENT_MAX_MB * 1024 * 1024,
        backupCount=PERSISTENT_BACKUP_COUNT,
    )
    persistent_handler.setLevel(logging.WARNING)
    persistent_handler.setFormatter(formatter)
    logger.addHandler(persistent_handler)

    # Under systemd, stdout goes to the journal — which is another write
    # stream on the same card. Keep the console useful when a human is
    # watching and quiet when one is not.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level_value if sys.stderr.isatty() else logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def InitializeConsoleLogging(level="INFO"):
    """
    Logging for the command line tools (splitflap/calibrate.py).

    Same logger tree as the service, so the drivers' own warnings show up, but
    printed to the console and written to no files: a tool run from a terminal
    has no business touching the SD card's log or the live log the dashboard
    tails.
    """
    level_value = _resolve_level(level)

    logger = logging.getLogger(_root_logger_name)
    logger.setLevel(level_value)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setLevel(level_value)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logger.addHandler(handler)
    return logger


def SetLogLevel(level) -> None:
    """
    Applies the configured log level once ConfigManager has loaded.

    Logging is initialised before the config file is read, so the `log_level`
    config key is applied afterwards. The persistent handler stays pinned at
    WARNING regardless — that split is the point of the design, not a default.
    """
    level_value = _resolve_level(level)
    logger = logging.getLogger(_root_logger_name)
    logger.setLevel(level_value)

    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            if os.path.basename(handler.baseFilename) == LOG_FILE_NAME:
                handler.setLevel(level_value)
        elif isinstance(handler, logging.StreamHandler) and sys.stderr.isatty():
            handler.setLevel(level_value)


def GetLiveLogPath() -> str:
    """Path of the log /api/logs should tail. Empty before initialisation."""
    return _live_log_path or LOG_FILE_NAME


def GetLogger(childName: str):
    """
    Creates a child logger that inherits the handlers from the base
    'AirspaceMonitor' logger.

    Usage: logger = GetLogger("FlightAware")
    """
    return logging.getLogger(f"{_root_logger_name}.{childName}")


def _resolve_level(level) -> int:
    if isinstance(level, int):
        return level
    resolved = logging.getLevelName(str(level).upper())
    return resolved if isinstance(resolved, int) else logging.INFO


def _usable_directory(path) -> str:
    """Returns `path` if we can actually write there, otherwise None."""
    if not path:
        return None
    try:
        os.makedirs(path, exist_ok=True)
        return path if os.access(path, os.W_OK) else None
    except Exception:
        return None
