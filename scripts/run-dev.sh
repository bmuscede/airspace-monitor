#!/bin/bash
# ---------------------------------------------------------
# Airspace Monitor Development Script
#
# This script sets up a user's environment to run the
# Airspace Monitor program locally. We set up both the
# dashboard and monitor service and then run it in a 
# dev only mode where we just fetch overhead flights from
# the FlightAware API at a specific interval.
# ---------------------------------------------------------

CURRENT_DIR="$(readlink -f $(dirname ${BASH_SOURCE[0]}))"
source "${CURRENT_DIR}/variables.sh"

echo "=============================================="
echo "     Airspace Monitor Development Runner      "
echo "=============================================="
echo ""

# Check for required host tools.
for tool in python3 npm; do
    if ! command -v $tool &> /dev/null; then
        echo "Error: Required tool '$tool' is not installed. Please install it and try again."
        exit 1
    fi
done

# Next, check if we have a Python virtual environment.
if [ ! -d "${ROOT_DIR}/venv" ]; then
    echo "Warning: Could not find Python virtual environment for monitor. Creating and installing dependencies..."

    python3 -m venv "${ROOT_DIR}/venv"
    if [ $? -ne 0 ]; then
        echo "Error: Could not install Python virtual environment to ${ROOT_DIR}/venv. Please try again."
        exit 1
    fi
    
    # Upgrade Pip and install dependencies.
    ${ROOT_DIR}/venv/bin/pip install --upgrade pip
    if [ $? -ne 0 ]; then
        echo "Error: Encountered an error upgrading 'pip'. Please check the error above and try again."
        exit 1
    fi
    if [ -f "${MONITOR_SERVICE_DIR}/requirements.txt" ]; then
        ${ROOT_DIR}/venv/bin/pip install -r "${MONITOR_SERVICE_DIR}/requirements.txt"
        if [ $? -ne 0 ]; then
            echo "Error: Encountered an error while trying to install requirements for Monitor Service. Please check the error above and try again."
            exit 1
        fi
    fi
fi

# Next, check the NPM Status
if [ ! -d "${MONITOR_DASHBOARD_DIR}/node_modules" ]; then
    echo "Warning: Could not find installed node modules for dashboard. Creating and installing dependencies..."
    
    cd "${MONITOR_DASHBOARD_DIR}"
    npm install
    if [ $? -ne 0 ]; then
        echo "Error: Encountered and error while installing requirements for Dashboard Service. Please check the error and try again."
        exit 1
    fi
fi

# Last, we need to start the two services. Both will run in the background.
# TODO!
