#!/bin/bash
# ---------------------------------------------------------
# Airspace Monitor Split-Flap Calibration Script
#
# Runs the hands-on part of building a split-flap display:
# measuring each module's home offset, stepping every module
# through every flap to check the charset matches the spool,
# and writing text to see where it lands.
#
# Only one program can hold the display's serial port, so
# this stops the monitor service first and starts it again
# on the way out.
#
# Usage: ./calibrate-splitflap.sh [COMMAND [ARGS...]]
#        (default command: calibrate)
#
# Run './calibrate-splitflap.sh --help' for every command.
# ---------------------------------------------------------

CURRENT_DIR="$(readlink -f $(dirname ${BASH_SOURCE[0]}))"
source "${CURRENT_DIR}/variables.sh"

SERVICE_NAME="airspace-monitor-service"
TOOL="${MONITOR_SERVICE_DIR}/splitflap/calibrate.py"
TOOL_MODULE="splitflap.calibrate"

echo "=============================================="
echo "    Airspace Monitor Split-Flap Calibration   "
echo "=============================================="
echo ""

if [ ! -f "${TOOL}" ]; then
    echo "Error: Could not find ${TOOL}. Run this script from the repository it came with."
    exit 1
fi

# Find a Python with the service's dependencies installed. The Pi keeps its
# virtual environment beside the service; a development checkout has one at the
# root (see run-dev.sh), and on Windows the interpreter is in Scripts/.
PYTHON_CANDIDATES=(
    "${MONITOR_SERVICE_DIR}/venv/bin/python"
    "${ROOT_DIR}/venv/bin/python"
    "${MONITOR_SERVICE_DIR}/venv/Scripts/python.exe"
    "${ROOT_DIR}/venv/Scripts/python.exe"
)

PYTHON=""
for candidate in "${PYTHON_CANDIDATES[@]}"; do
    if [ -x "${candidate}" ]; then
        PYTHON="${candidate}"
        break
    fi
done

if [ -z "${PYTHON}" ]; then
    if command -v python3 &> /dev/null; then
        echo "Warning: No virtual environment found. Using the system python3, which needs the"
        echo "         monitor service's requirements installed (pyserial, pydantic)."
        PYTHON="python3"
    else
        echo "Error: Could not find a Python interpreter. Install python3 and try again."
        exit 1
    fi
fi

# The service holds the serial port open while it is running, so it has to go
# down for the duration. Remember whether we stopped it so we can be polite
# about putting it back.
SERVICE_WAS_RUNNING=0
if command -v systemctl &> /dev/null; then
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo "Stopping ${SERVICE_NAME} so it releases the display's serial port..."
        if ! sudo systemctl stop "${SERVICE_NAME}"; then
            echo "Error: Could not stop ${SERVICE_NAME}. Stop it by hand and try again:"
            echo "  sudo systemctl stop ${SERVICE_NAME}"
            exit 1
        fi

        # The service catches SIGTERM and flushes its open contacts before it
        # exits, so give it a moment to actually let go of the port.
        sleep 2
        SERVICE_WAS_RUNNING=1
        echo ""
    fi
fi

restart_service() {
    if [ "${SERVICE_WAS_RUNNING}" -eq 1 ]; then
        echo ""
        echo "Starting ${SERVICE_NAME} again..."
        sudo systemctl start "${SERVICE_NAME}"
    fi
}

# Put the service back even if the calibration is interrupted part way through.
trap 'restart_service' EXIT

# Default to the interactive calibration, which is what people are here for.
if [ $# -eq 0 ]; then
    set -- calibrate
fi

cd "${MONITOR_SERVICE_DIR}"
"${PYTHON}" -m "${TOOL_MODULE}" --config_dir "${MONITOR_SERVICE_DIR}" "$@"
EXIT_CODE=$?

if [ ${EXIT_CODE} -ne 0 ]; then
    echo ""
    echo "Warning: ${TOOL_MODULE} exited with code ${EXIT_CODE}. Nothing was saved unless it said so above."
fi

exit ${EXIT_CODE}
