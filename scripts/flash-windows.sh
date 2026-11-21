#!/bin/bash
# ---------------------------------------------------------
# Airspace Monitor Flash Script for Windows (Git Bash)
#
# This script downloads the OS image and helps you inject
# configurations after you manually flash it.
# ---------------------------------------------------------

CURRENT_DIR="$(readlink -f "$(dirname "${BASH_SOURCE[0]}")")"
source "${CURRENT_DIR}/variables.sh"

# The SD card is already mounted as a drive letter and writable by the current
# user, so nothing here needs elevating. Set before common.sh is sourced.
SUDO=""
source "${CURRENT_DIR}/common.sh"

echo "=============================================="
echo "  Airspace Monitor SD Card Provisioner (Win)  "
echo "=============================================="
echo ""

# Check for required host tools.
require_tools curl xz awk mktemp tr

# Download and cache the DietPi image.
fetch_image
echo ""

# Gather everything the headless first boot needs.
read_install_mode
read_location_hints
read_network_credentials
read_appliance_settings

echo "============================================================"
echo " MANUAL FLASHING REQUIRED"
echo "============================================================"
echo "Since you are on Windows, you must manually flash the drive."
echo "Please follow these steps:"
echo ""
echo "1. Download and install Raspberry Pi Imager or Rufus."
echo "2. Open the imager and select 'Use custom' for the OS."
echo "3. Select this extracted image file:"
if command -v cygpath &> /dev/null; then
    echo "   $(cygpath -w "${OS_CACHE_DIR}/${IMG_NAME}")"
else
    echo "   ${OS_CACHE_DIR}/${IMG_NAME}"
fi
echo "4. Select your SD card as the storage."
echo "5. Flash the image (do NOT apply OS customization settings in Pi Imager)."
echo "6. Once finished, Windows may complain about formatting. IGNORE IT."
echo "7. Remove and re-insert the SD card into your computer."
echo "8. Identify the Drive Letter (e.g., E or F) that Windows assigned"
echo "   to the 'boot' partition."
echo "============================================================"
echo ""
read -p "Press Enter when you have completed the above steps and re-inserted the SD card..."
echo ""

read -p "Enter the drive letter of the SD card (e.g., E): " DRIVE_LETTER

# Clean up input in case user entered 'E:', 'E:\', or just 'E'
DRIVE_LETTER=$(echo "$DRIVE_LETTER" | tr -d ':\\/' | tr '[:upper:]' '[:lower:]')
if ! [[ "${DRIVE_LETTER}" =~ ^[a-z]$ ]]; then
    echo "Error: '${DRIVE_LETTER}' is not a drive letter. Enter a single letter, e.g. E."
    exit 1
fi
MOUNT_DIR="/${DRIVE_LETTER}"

if [ ! -f "${MOUNT_DIR}/dietpi.txt" ]; then
    echo "Error: Could not find dietpi.txt on drive ${DRIVE_LETTER}:."
    echo "Are you sure this is the right drive and the SD card was re-inserted?"
    exit 1
fi

# Write our automation settings, Wi-Fi details and first-boot script. This is
# the same code the Linux path runs, so the two cannot drift apart.
inject_boot_config "${MOUNT_DIR}"

# Windows holds writes in cache, and the card is usually pulled straight after
# this. Flush before telling anyone it is safe to remove.
sync

echo ""
echo "=============================================="
echo " SUCCESS! The SD card is fully provisioned.   "
echo ""
echo " Eject the card from Windows before removing  "
echo " it, then plug it into the Raspberry Pi,      "
echo " plug the Pi into power, and wait ~10 mins    "
echo " for it to silently install everything.       "
echo "=============================================="
