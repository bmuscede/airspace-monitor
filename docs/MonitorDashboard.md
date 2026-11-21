# Monitor Dashboard (Frontend)

## Overview

The monitor-dashboard is the web-based Command Center for the Airspace Monitor project. It provides a visual interface to track overhead flights, configure backend settings, view live system logs, toggle hardware display modes, and perform system administration tasks directly on the Raspberry Pi without needing SSH access.

## Tech Stack

* **Framework:** React 18 with TypeScript
* **Build Tool:** Vite
* **Styling:** Tailwind CSS v4 (Glassmorphism aesthetics)
* **Icons:** Lucide React

## Architecture

The dashboard is decoupled from the hardware controller. During development, it runs as a standalone Vite application (port 5173). In production, it is built into static files (`dist/`) that are served directly by the Python backend.

The application utilizes a lightweight, state-based routing approach via a Sidebar navigation menu. The drawer carries four destinations, with Settings holding four sections behind a chevron:
1. **Dashboard:** Live airspace map and active target lists.
2. **History:** Past contacts. The endpoints exist (`/api/history/contacts`, `/api/history/stats`) but the view does not, so the destination is shown disabled.
3. **Logs:** A real-time system console viewer.
4. **Settings → Backend / Split-Flap / Network / System:** One page per area rather than a single configuration hub.

## Key Components

1. **Navigation Drawer:** Persistent menu providing quick access between Dashboard, History, Live Logs and the four Settings sections, while displaying the overarching service status. The Settings group opens when one of its pages is showing and can be collapsed with its chevron. The footer pill reads Online, Offline or Checking — a service that cannot be reached is reported as offline rather than leaving the last good state on screen.

2. **Live Airspace Radar (Dashboard):** A CSS-animated radar view that plots aircraft distance and bearing relative to the current antenna position. Shown as a radar display.

3. **Overhead Targets (Dashboard):** A list view displaying real-time telemetry (Altitude, Speed, Distance, Aircraft Type) fetched from the backend.

4. **Live Logs Viewer:** A dedicated page acting as a system console. Displays live `readsb`, API, and system events with interactive filters for Debug, Info, Warning, and Error levels.

5. **Settings → Backend:** Receiver position and range, the FlightAware and OpenWeatherMap credentials and cache lifetimes, the three `history.*` values and the live log level. Fields are validated before they can be saved, the header counts unsaved changes, and only the dotted keys that changed are sent to `POST /api/config`. Shortening history retention confirms first, since it deletes rows on the service's next sweep.

6. **Settings → Split-Flap:** Rows and flaps with a character set and Chainlink channel per flap, the character sets themselves (editable, with a token-aware bulk field where `{ACA}` is one flap), auto re-home limits, and calibration. Duplicate or out-of-range channels are refused here rather than written, because a wrong channel fails silently on the hardware.

7. **Settings → Network:** The saved `wpa_supplicant` networks, with add and remove wired to `/api/wifi`. Both now report success and failure instead of passing in silence; removal confirms, because the request that removes a network may be travelling over it.

8. **Settings → System:** Service state, hardware output (Split-Flap or E-Ink), the software and data actions, and the power actions.

9. **Error Modals:** `ErrorDialogProvider` shows any failed action as a modal carrying the service's own output — toasts are kept for successes, since a toast that expires is the wrong way to report a save that did not happen. Polling failures stay in the console; the drawer's status pill is the signal for a service that has gone quiet.

## System Administration

Available on the Settings → System page, allowing for rapid system management:
1. **Update Codebase:** Triggers a `git pull` via the Python backend to fetch the latest code.
2. **Update Aircraft DB:** Initiates a background download of the latest OpenSky CSV database.
3. **Restart Services:** Restarts the underlying Python service without requiring a full OS reboot. Confirms first.
4. **Shut Down:** Stops the service cleanly via `POST /api/shutdown`, which flushes open contacts and closes the history database. Confirms first, and says that only a power cycle brings it back.

## Not Wired Up Yet

Drawn in the design and present in the UI as disabled controls, each marked with a `TODO: This is a stub` comment beside it. None of them can be saved or run today, so none of them pretend to work:

* **History view** — the endpoints exist, the view does not.
* **Split-Flap:** the live display read (what is on the flaps, firmware version, resolved port), the three test actions, per-module health, quiet hours (six config keys the service does not define), adding or removing a character set and the per-set fallback flap (`POST /api/config` only sets keys the service already defines), and re-running calibration.
* **Network:** the Connection panel (associated SSID, signal, IP, hostname, link uptime) and per-network in-range state, which need `iwgetid`, `iwconfig`, `hostname -I` and `wpa_cli scan_results`.
* **System:** commit and branch, service uptime and start time, the aircraft CSV's row count and date, the log and history database sizes, and an endpoint that serves the log file.

## Development Setup

The `vite.config.ts` file includes a proxy configuration. Any fetch requests made to `/api/*` are automatically forwarded to `http://127.0.0.1:8000` to prevent CORS errors while testing against the local Python FastAPI server.

```bash
# Install dependencies
npm install

# Run local development server
npm run dev

# Build for production
npm run build
```