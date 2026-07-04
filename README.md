# ✈️ Airspace Monitor

**Airspace Monitor** is an ADS-B overhead flight tracking system designed for Raspberry Pi (DietPi OS). It detects live aircraft traffic overhead using an ADS-B antenna and receiver, enriches flight data with origin/destination details via FlightAware's AeroAPI, and outputs real-time flight telemetry to physical displays (**E-Ink** and mechanical **Split-Flap**) as well as a modern web-based **Command Center Dashboard**.

---

## 📌 Project Overview

```
                          ┌────────────────────────┐
                          │     ADS-B Antenna      │
                          └───────────┬────────────┘
                                      │ (RTL-SDR)
                                      ▼
                          ┌────────────────────────┐
                          │     readsb Decoder     │
                          └───────────┬────────────┘
                                      │ (JSON Telemetry)
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           monitor-service (Python)                        │
│                                                                           │
│   ┌───────────────────┐    ┌────────────────────┐   ┌─────────────────┐   │
│   │ OpenSky ICAO CSV  │    │ FlightAware API    │   │ FastAPI Server  │   │
│   │ (Local Hex Lookup)│    │ (TTL Cache Routes) │   │ (Port 8000)     │   │
│   └───────────────────┘    └────────────────────┘   └────────┬────────┘   │
└─────────────┬───────────────────────────┬────────────────────┼────────────┘
              │ (SPI)                     │ (I2C)              │
              ▼                           ▼                    ▼ (HTTP/REST)
    ┌──────────────────┐        ┌───────────────────┐┌──────────────────┐
    │  E-Ink Display   │        │ Split-Flap Display││  React Dashboard │
    │ (Silent / Static)│        │ (Mechanical Flaps)││ (Airspace Radar) │
    └──────────────────┘        └───────────────────┘└──────────────────┘
```

---

## ✨ Key Features

- **Live ADS-B Aircraft Tracking:** Ingests raw 1090MHz ADS-B radio signals using `readsb` to decode aircraft hex codes, speed, altitude, heading, bearing, and distance in real time.
- **Dual Display Support:**
  - 🖼️ **E-Ink Display:** Silent, high-contrast, low-power display via SPI interface (`spidev` + Pillow PIL image renderer).
  - 🔢 **Split-Flap Display:** Tactile mechanical flap display driven via I2C (`smbus2` with MCP23017 expanders & stepper motor controllers).
- **Fast Local Data Enrichment:**
  - **Local ICAO Database:** Fast offline lookups of aircraft tail numbers, manufacturers, and model types via a cached 50MB OpenSky database CSV.
  - **FlightAware AeroAPI Integration:** Fetches flight origin/destination airport IATA codes (e.g., `YOW` -> `LHR`) with Time-To-Live (TTL) memory caching to minimize API calls for loitering aircraft.
- **Modern Web Dashboard (React + Vite):**
  - **Multi-View Interface:** State-based sidebar navigation with premium glassmorphism styling.
  - **Airspace Radar:** CSS-animated real-time radar view plotting overhead aircraft relative to receiver coordinates.
  - **Live Targets List:** Detail view displaying altitude, speed, bearing, flight numbers, and route details.
  - **Live System Logs:** Dedicated console viewer with interactive log level filters (Debug, Info, Warning, Error).
  - **Settings & Administration:** Dedicated interface to update `config.py` variables, trigger git updates, switch physical displays, connect to Wi-Fi, and restart services without SSH.
- **Automated OS Deployment:** Includes shell scripts to provision and flash DietPi OS to an SD card with headless automated setup.

---

## 📁 Repository Structure

```
.
├── monitor-service/     # Python FastAPI backend service & hardware drivers
│   ├── controller.py    # Core entry point (FastAPI server + hardware daemon thread)
│   ├── api.py           # REST API routes for dashboard & configuration
│   ├── aircraft_db.py   # Local ICAO hex lookup & OpenSky database manager
│   ├── flightaware.py   # FlightAware AeroAPI client with TTL caching
│   ├── eink.py          # E-Ink driver (SPI / Pillow rendering)
│   └── splitflap.py     # Split-Flap driver (I2C / MCP23017 stepper control)
├── monitor-dashboard/   # React 18 + TypeScript + Vite + Tailwind CSS v4 dashboard
│   ├── src/             # Radar view, target lists, hardware toggles, & settings UI
│   └── vite.config.ts   # Development API proxy configuration (forwarding to port 8000)
├── data/                # Local data files
│   └── aircraft_database.csv  # ICAO 24-bit hex lookup database
├── os/                  # OS provisioning & automated setup
│   └── setup.sh         # First-boot bash script executed on DietPi
├── scripts/             # Host utility scripts & testing helpers
│   ├── flash.sh         # Interactive bash script to flash DietPi to SD card
│   └── variables.sh     # Flashing & OS download configuration variables
└── docs/                # Component documentation
    ├── MonitorService.md   # Service architecture & API breakdown
    └── MonitorDashboard.md # Frontend architecture & component details
```

---

## 🛠️ Hardware & OS Requirements

- **Base Unit:** Raspberry Pi (3B+, 4, 5, or Zero 2 W recommended) running **DietPi OS**.
- **Radio Receiver:** RTL-SDR USB dongle + 1090 MHz ADS-B antenna.
- **Displays (Optional / Configurable):**
  - SPI E-Ink Display (e.g., Waveshare E-Paper).
  - I2C Split-Flap Display with MCP23017 port expanders.

---

## 🚀 Getting Started

### Option 1: Automated SD Card Flashing (Recommended)

Use the interactive flashing script in `scripts/` from your host machine to prepare an SD card for headless setup:

```bash
cd scripts
bash flash.sh
```

The script will:
1. Download and cache the latest DietPi OS image.
2. Interactively prompt for the target SD card drive and your local Wi-Fi credentials.
3. Inject `os/setup.sh` as an automated first-boot script.
4. On first power up, the Raspberry Pi will automatically install system dependencies, `readsb` ADS-B decoder, setup Python environment, and register the systemd service.

### Option 2: Manual Installation on DietPi

If you already have a running DietPi installation on your Raspberry Pi:

```bash
# Clone the repository
git clone https://github.com/bmuscede/airspace-monitor.git /opt/airspace-monitor
cd /opt/airspace-monitor

# Run the OS setup script
chmod +x os/setup.sh
sudo os/setup.sh
```

---

## 💻 Local Development & Testing

You can run the frontend dashboard and backend service locally in test mode while developing.

### 1. Running the `monitor-service` Backend

```bash
cd monitor-service

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install fastapi uvicorn requests smbus2 spidev RPi.GPIO Pillow

# Run the backend dev server (port 8000)
uvicorn controller:app --reload --port 8000
```

### 2. Running the `monitor-dashboard` Frontend

```bash
cd monitor-dashboard

# Install dependencies
npm install

# Start Vite dev server (port 5173 with proxy to http://127.0.0.1:8000)
npm run dev
```

Open `http://localhost:5173` in your browser to view the Command Center.

---

## 📖 Component Documentation

For detailed technical breakdowns of individual components, refer to the `docs/` directory:

- [Monitor Service Architecture](docs/MonitorService.md) — Multi-threading, FastAPI endpoints, FlightAware API integration, and hardware driver details.
- [Monitor Dashboard Overview](docs/MonitorDashboard.md) — React component architecture, radar view math, state management, and administrative controls.

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.