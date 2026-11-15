import subprocess
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, RootModel
from starlette.concurrency import run_in_threadpool

from utils.config import FlattenKeys
from utils.logs import GetLogger, GetLiveLogPath, SetLogLevel

# Module-level reference to the Controller.
# Set by controller.py at startup before uvicorn.run().
controller = None

logger = GetLogger("API")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Secondary shutdown hook.

    SIGTERM/SIGINT are the primary route; this catches the case where uvicorn
    is torn down without a signal reaching our handler. Shutdown() is
    idempotent, so overlapping routes are harmless. It blocks waiting for the
    hardware thread to flush, so run it off the event loop.
    """
    yield
    if controller is not None:
        await run_in_threadpool(controller.Shutdown)


app = FastAPI(title="Airspace Monitor Service API", lifespan=lifespan)

# Allow the React dashboard (Vite dev server) to make requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigUpdate(RootModel[Dict[str, Any]]):
    """
    Partial config update.

    The config is nested, so this is a free-form object rather than a field per
    setting: a caller can send {"radar": {"home_lat": 45.0}} or the flat
    {"radar.home_lat": 45.0}, and either way only the keys it sends are
    touched. Keys the config doesn't define are left alone and listed back in
    the response as "ignored", so a typo can't quietly add a setting nothing
    reads.
    """
    root: Dict[str, Any] = {}

class WifiAddRequest(BaseModel):
    ssid: str
    password: str


@app.get("/api/flights")
def get_flights():
    """Returns all aircraft currently within radar range."""
    return controller.GetAircraft()

@app.get("/api/state")
def get_state():
    """Returns a snapshot of the full system state."""
    return controller.GetState()

@app.post("/api/mode")
def toggle_mode():
    """Toggles between E-Ink and Split-Flap display modes."""
    new_mode = controller.ToggleDisplayMode()
    return {"mode": new_mode}

@app.get("/api/config")
def get_config():
    """Returns the current application configuration."""
    return controller.configManager.GetAll()

@app.post("/api/config")
def save_config(update: ConfigUpdate):
    """
    Sets the provided config fields in memory and persists to disk.
    Only the keys sent are applied, and null values are ignored.
    """
    # Nested objects are flattened to the dotted keys ConfigManager.Set()
    # takes, so {"radar": {"home_lat": 45.0}} sets radar.home_lat without
    # replacing the rest of the radar object.
    changes = {k: v for k, v in FlattenKeys(update.root).items() if v is not None}

    ignored = [key for key in changes if not controller.configManager.Has(key)]
    for key in ignored:
        logger.warning(f"Ignoring unknown config key: {key}")
        changes.pop(key)

    if not changes:
        return {"status": "no changes", "ignored": ignored}

    # Set each changed value in the in-memory config.
    for key, value in changes.items():
        controller.configManager.Set(key, value)

    # A few keys are held by live objects rather than read per use, so apply
    # them now instead of waiting for a restart.
    if "log_level" in changes:
        SetLogLevel(changes["log_level"])
    if "history.contact_gap_seconds" in changes:
        controller.tracker.contact_gap_seconds = changes["history.contact_gap_seconds"]
    if "history.flush_seconds" in changes:
        controller.history.flush_seconds = changes["history.flush_seconds"]
    if "history.retention_days" in changes:
        controller.history.retention_days = changes["history.retention_days"]

    # Persist the updated config to disk.
    success = controller.configManager.SaveConfig()
    return {"status": "saved" if success else "error", "ignored": ignored}


@app.get("/api/history/contacts")
def get_history_contacts(
    before: Optional[float] = Query(None, description="Return contacts with last_seen before this timestamp."),
    before_id: Optional[int] = Query(None, description="Tie-breaker rowid for identical last_seen values."),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Recent completed contacts, most recent first.

    Keyset-paginated rather than OFFSET-paginated: rows are inserted underneath
    the cursor as aircraft come and go, and offset pagination silently skips
    and repeats rows under exactly those conditions. Page forward by passing
    the `next_before` / `next_before_id` values from the previous response.
    """
    return controller.GetHistoryContacts(before=before, before_id=before_id, limit=limit)

@app.get("/api/history/stats")
def get_history_stats(range: str = Query("today", pattern="^(today|week|all)$")):
    """
    Aggregate history stats for a range, computed in SQL — contact count,
    distinct aircraft, closest approach and which aircraft made it, and the
    busiest hour of the day.
    """
    return controller.GetHistoryStats(range)

@app.get("/api/wifi")
def get_wifi_networks():
    """Lists all Wi-Fi networks configured in wpa_supplicant."""
    return controller.configManager.GetWifiNetworks()

@app.post("/api/wifi")
def add_wifi_network(req: WifiAddRequest):
    """Adds a new Wi-Fi network to wpa_supplicant."""
    success = controller.configManager.AddWifiNetwork(req.ssid, req.password)
    return {"status": "added" if success else "error", "ssid": req.ssid}

@app.delete("/api/wifi/{ssid}")
def remove_wifi_network(ssid: str):
    """Removes a Wi-Fi network from wpa_supplicant by SSID."""
    success = controller.configManager.RemoveWifiNetwork(ssid)
    return {"status": "removed" if success else "error", "ssid": ssid}

@app.post("/api/git-pull")
def git_pull():
    """Executes a git pull to update the codebase on the Pi."""
    logger.info("Executing git pull...")
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd="/opt/airspace-monitor",
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip() or result.stderr.strip()
        logger.info(f"git pull result: {output}")
        return {"status": "success" if result.returncode == 0 else "error", "output": output}
    except subprocess.TimeoutExpired:
        logger.error("git pull timed out.")
        return {"status": "error", "output": "Command timed out."}
    except Exception as e:
        logger.error(f"git pull failed: {e}")
        return {"status": "error", "output": str(e)}

@app.post("/api/update-db")
def update_aircraft_db(background_tasks: BackgroundTasks):
    """
    Triggers a background download of the latest OpenSky aircraft database.
    Uses FastAPI's BackgroundTasks so the HTTP response returns immediately.
    """
    if controller.aircraftDB.isUpdating:
        return {"status": "already_updating"}

    background_tasks.add_task(controller.aircraftDB.DownloadDatabase)
    logger.info("Aircraft database update started in background.")
    return {"status": "started"}

@app.post("/api/restart-service")
def restart_service():
    """Restarts the airspace-monitor systemd service."""
    logger.info("Restarting airspace-monitor service...")
    try:
        # systemctl restart sends SIGTERM, which Controller._install_signal_handlers
        # routes into the same clean shutdown path as /api/shutdown, so open
        # contacts are flushed before the process goes away.
        result = subprocess.run(
            ["systemctl", "restart", "airspace-monitor-service"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {"status": "success" if result.returncode == 0 else "error"}
    except Exception as e:
        logger.error(f"Service restart failed: {e}")
        return {"status": "error", "output": str(e)}

@app.post("/api/shutdown")
def shutdown():
    """
    Gracefully shuts down the controller's hardware loop.

    Blocks until the hardware thread has flushed open contacts and closed the
    database, so the caller knows the write actually happened.
    """
    controller.Shutdown()
    return {"status": "shutting_down"}

@app.get("/api/logs")
def get_logs():
    """
    Returns the most recent log entries from the live (tmpfs) log.
    Reads the tail of the log file and returns the last 200 lines.
    """
    log_file = GetLiveLogPath()
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()

        recent = lines[-200:]
        entries = []
        for i, line in enumerate(recent):
            line = line.strip()
            if not line:
                continue

            # Parse log format: "2025-07-04 12:00:01 [INFO] [Controller] Message"
            parts = line.split(" ", 4)
            if len(parts) >= 5:
                timestamp = f"{parts[0]} {parts[1]}"
                level = parts[2].strip("[]")
                source = parts[3].strip("[]")
                message = parts[4]
            else:
                timestamp = ""
                level = "INFO"
                source = "system"
                message = line

            entries.append({
                "id": i,
                "timestamp": timestamp,
                "level": level,
                "message": message,
                "source": source,
            })

        return entries

    except FileNotFoundError:
        return []
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return []
