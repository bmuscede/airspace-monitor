# Monitor Service

## Overview

The monitor-service is the core orchestrator of the Airspace Monitor project. Running on a headless Raspberry Pi (DietPi), it handles live ADS-B data ingestion, external API routing, background database management, and physical hardware control (I2C/SPI).

## Tech Stack

* **Language:** Python 3
* **Web Framework:** FastAPI with Uvicorn
* **Hardware Libraries:** smbus2 (I2C for Split-Flaps), spidev (SPI for E-Ink), RPi.GPIO
* **Data Processing:** requests, csv

## Core Modules

### controller.py (The Orchestrator)

The entry point of the application. It utilizes Python's threading module to solve the blocking issue of hardware loops:

* **Main Thread:** Runs the FastAPI web server (uvicorn) on port 8000, listening for React dashboard requests.
* **Daemon Thread:** Runs the hardware_loop() continuously in the background, polling readsb JSON data and pushing updates to the active physical display.

### api.py (The Web Interface)

Defines the REST endpoints consumed by the React dashboard.

Some examples of the API are as follows:
* GET /api/flights: Returns active overhead flights.
* POST /api/mode: Toggles between 'E-Ink' and 'Split-Flap'.
* POST /api/git-pull: Executes an OS-level subprocess call to update the repo.
* POST /api/update-db: Uses FastAPI's BackgroundTasks to download the 50MB aircraft database without blocking the UI.

### aircraft_db.py (Local Caching)

Manages the OpenSky Network aircraft database. Loads the CSV of ADS-B hex codes in `data/aircraft_database.csv` and uses that to get aircraft types and tail numbers locally instead of hitting the FlightAware API for every flight.

### flightaware.py (External Routing)

Wraps the FlightAware AeroAPI.

Used exclusively to fetch Origin/Destination IATA codes (e.g., YOW -> LHR), as this data is not broadcasted via raw ADS-B.

Includes a Time-To-Live (TTL) memory cache to prevent redundant API calls for flights loitering in the airspace.

### Hardware Drivers

1. eink.py: Handles SPI communication and Pillow (PIL) image generation for the E-Ink dashboard.

2. splitflap.py: Handles I2C communication with the MCP23017 expanders and Stepper Motor logic for the mechanical display.