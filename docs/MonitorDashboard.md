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

The application utilizes a lightweight, state-based routing approach via a Sidebar navigation menu. It separates the interface into three main views:
1. **Dashboard:** Live airspace map and active target lists.
2. **Logs:** A real-time system console viewer.
3. **Settings:** A configuration hub for adjusting variables and managing the system.

## Key Components

1. **Sidebar Navigation:** Persistent menu providing quick access between Dashboard, Logs, and Settings while displaying the overarching service status.

2. **Live Airspace Radar (Dashboard):** A CSS-animated radar view that plots aircraft distance and bearing relative to the current antenna position. Shown as a radar display.

3. **Overhead Targets (Dashboard):** A list view displaying real-time telemetry (Altitude, Speed, Distance, Aircraft Type) fetched from the backend.

4. **Live Logs Viewer:** A dedicated page acting as a system console. Displays live `readsb`, API, and system events with interactive filters for Debug, Info, Warning, and Error levels.

5. **Settings Configuration:** A dedicated page sending API requests to the Python controller. Allows users to modify variables directly stored in `config.py` (e.g., AeroAPI Key, Cache TTL, Radar Range), and manage Wi-Fi networks configured in `wpa_supplicant.conf` with full add/remove support.

6. **Hardware Configuration (Settings):** Switches the physical output between the Split-Flap (noisy/mechanical) and E-Ink (silent/static) displays.

## System Administration

Available within the Settings page, allowing for rapid system management:
1. **Update Codebase:** Triggers a `git pull` via the Python backend to fetch the latest code.
2. **Update Aircraft DB:** Initiates a background download of the latest OpenSky CSV database.
3. **Restart Services:** Restarts the underlying Python service without requiring a full OS reboot.

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