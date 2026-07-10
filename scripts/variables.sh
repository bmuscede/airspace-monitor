#!/bin/bash
# ---------------------------------------------------------
# Variables for Runtime Scripts
#
# Change any variables here to update any scripts that use
# these variables.
# ---------------------------------------------------------

# Common directories for this repo.
ROOT_DIR="$(readlink -f ${CURRENT_DIR}/../)"
MONITOR_SERVICE_DIR="${ROOT_DIR}/monitor-service"
MONITOR_DASHBOARD_DIR="${ROOT_DIR}/monitor-dashboard"
OS_CACHE_DIR="${ROOT_DIR}/os/cache"

# The stable 64-bit DietPi image for Raspberry Pi
IMAGE_URL="https://dietpi.com/downloads/images/DietPi_RPi234-ARMv8-Trixie.img.xz"
ARCHIVE_NAME="DietPi_RPi234-ARMv8-Trixie.img.xz"
IMG_NAME="DietPi_RPi234-ARMv8-Trixie.img"