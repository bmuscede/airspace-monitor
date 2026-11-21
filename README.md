# Airspace Monitor

**Airspace Monitor** is an ADS-B overhead flight tracking system designed for Raspberry Pi (DietPi OS). 

It detects live aircraft traffic overhead using an ADS-B antenna and receiver, enriches flight data with origin/destination details via FlightAware's AeroAPI, and outputs real-time flight telemetry to physical displays (**E-Ink** and mechanical **Split-Flap**) as well as a modern web-based **Command Center Dashboard** for viewing all flights and for setting configuration parameters.

---

## Project Overview

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
└─────────────┬────────────────────────┬───────────────────────┼────────────┘
              │ (SPI)                  │ (USB serial)          │
              ▼                        ▼                       ▼ (HTTP/REST)
    ┌──────────────────┐     ┌───────────────────┐    ┌──────────────────┐
    │  E-Ink Display   │     │ Split-Flap Display│    │  React Dashboard │
    │ (Silent / Static)│     │ (Mechanical Flaps)│    │ (Airspace Radar) │
    └──────────────────┘     └───────────────────┘    └──────────────────┘
```

---

## Key Features

- **Live ADS-B Aircraft Tracking:** Ingests raw 1090MHz ADS-B radio signals using `readsb` to decode aircraft hex codes, speed, altitude, heading, bearing, and distance in real time.
- **Dual Display Support:**
  - 🖼️ **E-Ink Display:** Silent, high-contrast, low-power display via SPI interface (`spidev` + Pillow PIL image renderer).
  - 🔢 **Split-Flap Display:** Tactile mechanical flap display (Scott Bezek's splitflap) driven over USB serial (`pyserial`), speaking the Chainlink/ESP32 firmware's protobuf protocol.
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
│   ├── splitflap.py     # Split-Flap display (layout & calibration state)
│   └── splitflap/       # Split-Flap device: config, protocol, driver
│       └── calibrate.py # Hands-on calibration & checks (command line tool)
├── monitor-dashboard/   # React 18 + TypeScript + Vite + Tailwind CSS v4 dashboard
│   ├── src/             # Radar view, target lists, hardware toggles, & settings UI
│   └── vite.config.ts   # Development API proxy configuration (forwarding to port 8000)
├── data/                # Local data files
│   └── aircraft_database.csv  # ICAO 24-bit hex lookup database
├── os/                  # OS provisioning & automated setup
│   └── setup.sh         # First-boot bash script executed on DietPi
├── scripts/             # Host utility scripts & testing helpers
│   ├── flash.sh         # Interactive bash script to flash DietPi to SD card (Linux/macOS)
│   ├── flash-windows.sh # Same, for Windows: fetches the image, you flash it, it provisions the card
│   ├── common.sh        # Image download & boot-partition provisioning shared by both flash scripts
│   ├── calibrate-splitflap.sh # Calibrate the Split-Flap (stops the service first)
│   └── variables.sh     # Flashing & OS download configuration variables
└── docs/                # Component documentation
    ├── MonitorService.md   # Service architecture & API breakdown
    └── MonitorDashboard.md # Frontend architecture & component details
```

---

## 🛠️ Hardware & OS Requirements

This repository is designed to work with the following hardware: 
- **Base Unit:** Raspberry Pi (3B+, 4, 5, or Zero 2 W recommended) running **DietPi OS**.
- **Radio Receiver:** RTL-SDR USB dongle + 1090 MHz ADS-B antenna.
- **Displays (Optional / Configurable):**
  - SPI E-Ink Display (e.g., Waveshare E-Paper).
  - Split-Flap Display (Chainlink driver boards + ESP32), connected by USB.

---

## Getting Started

### Option 1: Automated SD Card Flashing (Recommended)

Use the interactive flashing script in `scripts/` from your host machine to prepare an SD card for headless setup.

On **Linux or macOS**, which can write the card directly:

```bash
cd scripts
bash flash.sh
```

On **Windows** (Git Bash), where the card is flashed by Raspberry Pi Imager or Rufus and this script provisions it afterwards:

```bash
cd scripts
bash flash-windows.sh
```

Both scripts will:
1. Download and cache the latest DietPi OS image.
2. Interactively prompt for everything a headless first boot needs (see below).
3. Write those settings, your network credentials and the receiver position into the boot partition, and inject `os/setup.sh` as an automated first-boot script.
4. On first power up, the Raspberry Pi will automatically enable SPI and I2C, install system dependencies, the `readsb` ADS-B decoder and the Python environment, seed `config.json` with the receiver position, register both systemd services, and reboot once so the SPI change takes effect.

The provisioning half is shared between the two scripts (`scripts/common.sh`), so the Windows and Linux paths cannot drift apart.

#### What the script asks for

| Prompt | Why it matters |
|---|---|
| **Location lookup** (optional) | Offers to ask ipinfo.io for an approximate position from your IP address, to prefill the three settings below. Off unless you ask for it, since it tells a third party your IP. Accurate to a town at best — always confirm it |
| **Network** | A Wi-Fi SSID, or blank to configure wired Ethernet instead. A blank password configures an open network (`keymgr=NONE`) |
| **Wi-Fi country code** | The regulatory domain. DietPi ships `GB`, and the wrong one can stop a Pi joining on the upper 2.4GHz channels — which on a headless board looks exactly like a bad password |
| **Login password** | Replaces DietPi's well-known default of `dietpi` for the `root` and `dietpi` users, on a board that accepts SSH. DietPi moves this out of `dietpi.txt` during first run setup |
| **Hostname** | Defaults to `airspace-monitor`, so the dashboard answers at `http://airspace-monitor.local:5173` instead of whatever address the router handed out |
| **Time zone** | The service timestamps every contact and rolls its daily counters over at local midnight. Left at DietPi's `UTC`, "today" rolls over at the wrong hour |
| **Receiver latitude/longitude** | Required. The service works out which aircraft are overhead from this, and shows whichever is **closest** — so a wrong position shows the wrong aircraft. It is seeded into `config.json` and passed to `readsb` on first boot. Without it the appliance comes up on the default `0.0, 0.0`, in the Atlantic, tracking nothing |

The scripts also set, without asking: OpenSSH instead of Dropbear (Dropbear has no sftp server, so `sftp` and any recent `scp` cannot copy the contact history off the Pi), continuous NTP sync, the DietPi survey opted out, and the serial console off — it otherwise prompts on first login, and the case covers the GPIO header, so it is not a recovery path that can be reached anyway.

The address is left on **DHCP**. Converting the lease to a static address pins the dashboard's URL, but it also stops the board renewing its lease, so it drops out of the router's device list and looks missing when it is merely busy — during a 30–60 minute first boot that is exactly when you want to watch it. Use a DHCP reservation on the router to pin the address instead.

> **Note:** DietPi gives Wi-Fi priority on first boot and disables Ethernet when both are configured, so a cable is not a fallback if the Wi-Fi credentials are wrong. Re-run the flashing script to fix them.
>
> `<hostname>.local` is mDNS, resolved directly between machines on the LAN — your router is not involved and does not need to support anything. `os/setup.sh` installs `avahi-daemon` and `libnss-mdns`, neither of which ships in the DietPi image, so the Pi can announce and resolve those names. It will not cross subnets or VLANs, and some access points filter the multicast it needs.

### Watching the first boot

First boot takes **30–60 minutes**, longer on a Pi Zero 2 W: `rtl-sdr` and `readsb` are both built from source and the dashboard runs `npm install`. The board stays reachable throughout and reboots exactly once, at the end.

`os/setup.sh` writes a timestamped progress log to **the boot partition** — `airspace-monitor-install.log`, next to `dietpi.txt`. That partition is FAT, so if the Pi cannot be reached you can power it down, put the card in any laptop and read the log there. Everything else the install writes lands on ext4, which Windows and macOS cannot read. Each line is flushed as it is written, so the log survives losing power mid-build.

The log records each phase (`[1/9]`…`[9/9]`), every failure, the board model, the final hostname and addresses, and `vcgencmd get_throttled` at both the start and the end of the install, decoded into plain words. That last one matters: a sustained compile plus an RTL-SDR dongle is the heaviest draw the board ever sees, and a marginal supply or a tired cable shows up as `undervoltage-has-occurred` and nowhere else. An undervolting Pi corrupts builds, wedges or reboots — all of which look like broken software from the outside.

If you are logged in while it runs, the full DietPi transcript is at `/var/lib/dietpi/logs/dietpi-firstrun-setup.log`, and `systemctl is-active dietpi-firstrun-setup` says whether it is still going. Logging in during the install shows a "waiting" loop from `dietpi-login`; pressing CTRL+C only exits that loop, and does not affect the install, which runs as a systemd service.

### Checking an install over SSH

Start with the install log. It is on the boot partition, so it is readable from the Pi too, and it names the phase that failed:

```
cat /boot/firmware/airspace-monitor-install.log
```

Then, in rough order of what tends to be wrong:

```
# Did the first-boot script finish, or is it still going?
systemctl is-active dietpi-firstrun-setup
tail -40 /var/lib/dietpi/logs/dietpi-firstrun-setup.log

# Is the project actually installed? /opt/airspace-monitor is the giveaway:
# if /opt/rtl-libs exists but this does not, the clone never happened.
ls -la /opt/airspace-monitor

# Our two services
systemctl status airspace-monitor-service airspace-monitor-dashboard
journalctl -u airspace-monitor-service -n 50 --no-pager

# The ADS-B feed everything depends on
systemctl status readsb
ls -la /run/readsb/aircraft.json

# Is SPI there? The E-Ink display needs it, and it only appears after a reboot.
ls -la /dev/spidev*
grep -E '^dtparam=(spi|i2c_arm)' /boot/firmware/config.txt

# Power and space, the two that masquerade as software faults
vcgencmd get_throttled
df -h /
```

If the install died partway, it can be re-run in place without reflashing the card — it is written to be repeatable, and will not overwrite an existing `config.json`:

```
bash /boot/firmware/Automation_Custom_Script.sh
```

### Bare mode: a card that installs nothing

The flashing script asks whether first boot should run the installer. Answer **no** and it writes a card that brings up a configured, reachable DietPi — password, Wi-Fi or Ethernet, hostname, time zone, OpenSSH — and then stops. `AUTO_SETUP_CUSTOM_SCRIPT_EXEC=0`, no `Automation_Custom_Script.sh` on the card, no services installed, nothing of this project's running.

This is the mode to flash when the board misbehaves during the install and you need to find out which step is responsible. `setup.sh` is still copied to the card as `airspace-monitor-setup.sh`, so it can be read and run a step at a time over SSH.

To go back, re-run the flashing script and answer **yes**. Nothing else needs changing.

#### Running the steps by hand

With a bare card, SSH in and work through `setup.sh`'s phases yourself. They are marked `[0/9]`…`[9/9]` in the file, so it can be followed top to bottom:

```
less /boot/firmware/airspace-monitor-setup.sh
```

The two phases worth suspecting first are the source builds, `[2/9]` RTL-SDR and `[3/9]` readsb, because they are long, they are third-party, and they install packages that overlap. Run the readsb one on its own and watch it:

```
wget -O /tmp/readsb-install.sh https://github.com/wiedehopf/adsb-scripts/raw/master/readsb-install.sh
less /tmp/readsb-install.sh
bash /tmp/readsb-install.sh
```

If the board stops responding during a step, these say what happened across the reboot:

```
journalctl --list-boots          # a new boot means something restarted it
last -x | head                   # reboots and shutdowns
journalctl -b -1 -e --no-pager   # the end of the previous boot
dmesg -T | grep -iE 'voltage|oom|killed process'
```

A step run under `script` keeps a transcript even if the session drops, which is the only way to see the last thing it printed before the board went away:

```
script -c "bash /tmp/readsb-install.sh" /root/readsb-attempt.log
```

> **The service code comes from GitHub, not from the card.** Only `setup.sh` itself is injected from your working tree; the install then clones `main` from the repository. Commits that exist only on your machine will not be on the Pi — push them first, or `git pull` inside `/opt/airspace-monitor` afterwards.

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

## Local Development & Testing

You can run the frontend dashboard and backend service locally in test mode while developing.

### 1. Running the `monitor-service` Backend

```bash
cd monitor-service

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install fastapi uvicorn requests pyserial spidev RPi.GPIO Pillow

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

## Component Documentation

For detailed technical breakdowns of individual components, refer to the `docs/` directory:

- [Monitor Service Architecture](docs/MonitorService.md) — Multi-threading, FastAPI endpoints, FlightAware API integration, and hardware driver details.
- [Monitor Dashboard Overview](docs/MonitorDashboard.md) — React component architecture, radar view math, state management, and administrative controls.

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
