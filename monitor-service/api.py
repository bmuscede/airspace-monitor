import subprocess
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logs

# Module-level reference to the Controller.
# Set by controller.py at startup before uvicorn.run().
controller = None

logger = logs.GetLogger("API")

app = FastAPI(title="Airspace Monitor Service API")

# Allow the React dashboard (Vite dev server) to make requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigUpdate(BaseModel):
    """Partial config update — only the fields sent will be merged."""
    flightaware_url: str = None
    flightaware_api_key: str = None
    cache_ttl: int = None
    home_lat: float = None
    home_lon: float = None
    max_radar_range_nm: int = None

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
    Only non-null fields are applied.
    """
    changes = {k: v for k, v in update.dict().items() if v is not None}

    if not changes:
        return {"status": "no changes"}

    # Set each changed value in the in-memory config.
    for key, value in changes.items():
        controller.configManager.Set(key, value)

    # Persist the updated config to disk.
    success = controller.configManager.SaveConfig()
    return {"status": "saved" if success else "error"}

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
        result = subprocess.run(
            ["systemctl", "restart", "airspace-monitor"],
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
    """Gracefully shuts down the controller's hardware loop."""
    controller.Shutdown()
    return {"status": "shutting_down"}

@app.get("/api/logs")
def get_logs():
    """
    Returns the most recent log entries from system.log.
    Reads the tail of the log file and returns the last 200 lines.
    """
    log_file = "system.log"
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
