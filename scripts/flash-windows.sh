#!/bin/bash
# ---------------------------------------------------------
# Airspace Monitor Flash Script for Windows (Git Bash)
#
# This script downloads the OS image and helps you inject
# configurations after you manually flash it.
# ---------------------------------------------------------

CURRENT_DIR="$(readlink -f $(dirname ${BASH_SOURCE[0]}))"
source "${CURRENT_DIR}/variables.sh"

echo "=============================================="
echo "  Airspace Monitor SD Card Provisioner (Win)  "
echo "=============================================="
echo ""

# Check for required host tools.
for tool in curl xz; do
    if ! command -v $tool &> /dev/null; then
        echo "Error: Required tool '$tool' is not installed. Please install it and try again."
        exit 1
    fi
done

# Download and cache the DietPi image.
if [ ! -f "${OS_CACHE_DIR}/${ARCHIVE_NAME}" ]; then
    echo "Downloading DietPi OS archive..."
    
    mkdir -p "${OS_CACHE_DIR}"
    curl -L -o "${OS_CACHE_DIR}/${ARCHIVE_NAME}" "${IMAGE_URL}"
    if [ $? -ne 0 ]; then
        echo "Error: Could not download DietPi to ${OS_CACHE_DIR}/${ARCHIVE_NAME}. Please try again later."
        exit 1
    fi

    echo "Using DietPi OS archive: ${ARCHIVE_NAME}"
else
    echo "Using cached DietPi OS archive: ${ARCHIVE_NAME}"
fi

if [ ! -f "${OS_CACHE_DIR}/${IMG_NAME}" ]; then
    echo "Extracting DietPi OS image..."
    xz -d -k "${OS_CACHE_DIR}/${ARCHIVE_NAME}"
    if [ $? -ne 0 ]; then
        echo "Error: Could not extract DietPi archive. Please try again later or manually extract it."
        exit 1
    fi
fi
echo ""

# Gather Wi-Fi credentials
read -p "Enter Wi-Fi SSID for the Pi: " WIFI_SSID
read -s -p "Enter Wi-Fi Password: " WIFI_PASS
echo ""
echo ""

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
MOUNT_DIR="/${DRIVE_LETTER}"

if [ ! -f "${MOUNT_DIR}/dietpi.txt" ]; then
    echo "Error: Could not find dietpi.txt on drive ${DRIVE_LETTER}:."
    echo "Are you sure this is the right drive and the SD card was re-inserted?"
    exit 1
fi

# Modify dietpi.txt for automation.
echo "Configuring dietpi.txt..."
sed -i.bak 's/^AUTO_SETUP_AUTOMATED=0/AUTO_SETUP_AUTOMATED=1/' "${MOUNT_DIR}/dietpi.txt"
sed -i.bak 's/^AUTO_SETUP_CUSTOM_SCRIPT_EXEC=0/AUTO_SETUP_CUSTOM_SCRIPT_EXEC=1/' "${MOUNT_DIR}/dietpi.txt"
sed -i.bak 's/^AUTO_SETUP_NET_WIFI_ENABLED=0/AUTO_SETUP_NET_WIFI_ENABLED=1/' "${MOUNT_DIR}/dietpi.txt"

# Modify dietpi-wifi.txt with user credentials.
echo "Configuring Wi-Fi credentials..."
sed -i.bak "s/^aWIFI_SSID\[0\]=''/aWIFI_SSID[0]='${WIFI_SSID}'/" "${MOUNT_DIR}/dietpi-wifi.txt"
sed -i.bak "s/^aWIFI_KEY\[0\]=''/aWIFI_KEY[0]='${WIFI_PASS}'/" "${MOUNT_DIR}/dietpi-wifi.txt"

# Inject the Automation_Custom_Script.sh directly into the boot partition.
cp "${ROOT_DIR}/os/setup.sh" "${MOUNT_DIR}/Automation_Custom_Script.sh"

echo ""
echo "=============================================="
echo " SUCCESS! The SD card is fully provisioned.   "
echo " You can now plug it into the Raspberry Pi,   "
echo " plug the Pi into power, and wait ~10 mins    "
echo " for it to silently install everything.       "
echo "=============================================="
