#!/bin/bash
# ---------------------------------------------------------
# Variables for Runtime Scripts
#
# Change any variables here to update any scripts that use
# these variables.
# ---------------------------------------------------------

# Common directories for this repo.
CURRENT_DIR="$(readlink -f $(dirname ${BASH_SOURCE[0]}))"
ROOT_DIR="$(readlink -f ${CURRENT_DIR}/../)"
OS_CACHE_DIR="${ROOT_DIR}/os/cache"

# The stable 64-bit DietPi image for Raspberry Pi
IMAGE_URL="https://dietpi.com/downloads/images/DietPi_RPi234-ARMv8-Trixie.img.xz"
ARCHIVE_NAME="DietPi_RPi234-ARMv8-Trixie.img.xz"
IMG_NAME="DietPi_RPi234-ARMv8-Trixie.img"