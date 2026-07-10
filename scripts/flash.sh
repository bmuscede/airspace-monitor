#!/bin/bash
# ---------------------------------------------------------
# Airspace Monitor Flash Script for Raspberry Pi
#
# This script flashes an SD card with the OS and tools to
# run Airspace Monitor on any Raspberry Pi.
# 
# Be careful of which SD card you select!!!
# ---------------------------------------------------------

CURRENT_DIR="$(readlink -f $(dirname ${BASH_SOURCE[0]}))"
source "${CURRENT_DIR}/variables.sh"

echo "=============================================="
echo "  Airspace Monitor SD Card Provisioner        "
echo "=============================================="
echo ""

# Check for required host tools.
for tool in curl xz dd; do
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

# Show the user which drive to target.
echo "============================================================"
echo "Available drives:"
if command -v lsblk &> /dev/null; then
    lsblk -d -o NAME,SIZE,MODEL | grep -v "loop"
else
    diskutil list | grep "external"
fi
echo ""
echo "CRITICAL: Choosing the wrong drive WILL erase your computer."
echo "============================================================"
read -p "Enter the target drive path (e.g., /dev/sdb, /dev/mmcblk0, or /dev/disk2): " TARGET_DRIVE

read -p "WARNING: ALL DATA ON ${TARGET_DRIVE} WILL BE DESTROYED. Type 'YES' to proceed: " CONFIRM
if [ "${CONFIRM}" != "YES" ]; then
    echo "Airspace Monitor will not be installed. Aborting."
    exit 1
fi
echo ""

# Gather Wi-Fi credentials
read -p "Enter Wi-Fi SSID for the Pi: " WIFI_SSID
read -s -p "Enter Wi-Fi Password: " WIFI_PASS
echo ""

# Prompt the user to install.
echo "============================================================"
echo "Ready to Flash Airspace Monitor"
echo ""
echo "Your Selections:"
echo "Image     - ${OS_CACHE_DIR}/${IMG_NAME}"
echo "Drive     - ${TARGET_DRIVE}"
echo "Wifi SSID - ${WIFI_SSID}"
echo "============================================================"

read -p "Do these settings look correct? Type 'YES' to proceed: " CONFIRM
if [ "${CONFIRM}" != "YES" ]; then
    echo "Airspace Monitor will not be installed. Aborting."
    exit 1
fi
echo ""

# Flash the image to the SD card.
echo "Flashing image to ${TARGET_DRIVE}... (This may take a few minutes. You may be prompted for your sudo password)"
sudo dd if="$IMG_NAME" of="${TARGET_DRIVE}" bs=4M status=progress
echo "Syncing filesystem..."
sync

# Mount the boot partition to inject configurations.
echo "Mounting boot partition to inject Wi-Fi and automation scripts..."
MOUNT_DIR="/tmp/dietpi_boot_$$"
mkdir -p "${MOUNT_DIR}"

# Determine the partition name based on standard naming conventions.
if [[ "${TARGET_DRIVE}" == *"mmcblk"* ]] || [[ "${TARGET_DRIVE}" == *"nvme"* ]]; then
    PARTITION="${TARGET_DRIVE}p1"
elif [[ "${TARGET_DRIVE}" == *"disk"* ]]; then
    PARTITION="${TARGET_DRIVE}s1"
else
    PARTITION="${TARGET_DRIVE}1"
fi

sudo mount "${PARTITION}" "${MOUNT_DIR}"
if [ $? -ne 0 ]; then
    echo "Error: Failed to mount ${PARTITION}. You may need to manually inject the files."
    exit 1
fi

# Modify dietpi.txt for automation.
echo "Configuring dietpi.txt..."
sudo sed -i.bak 's/^AUTO_SETUP_AUTOMATED=0/AUTO_SETUP_AUTOMATED=1/' "${MOUNT_DIR}/dietpi.txt"
sudo sed -i.bak 's/^AUTO_SETUP_CUSTOM_SCRIPT_EXEC=0/AUTO_SETUP_CUSTOM_SCRIPT_EXEC=1/' "${MOUNT_DIR}/dietpi.txt"
sudo sed -i.bak 's/^AUTO_SETUP_NET_WIFI_ENABLED=0/AUTO_SETUP_NET_WIFI_ENABLED=1/' "${MOUNT_DIR}/dietpi.txt"

# Modify dietpi-wifi.txt with user credentials.
echo "Configuring Wi-Fi credentials..."
sudo sed -i.bak "s/^aWIFI_SSID\[0\]=''/aWIFI_SSID[0]='${WIFI_SSID}'/" "${MOUNT_DIR}/dietpi-wifi.txt"
sudo sed -i.bak "s/^aWIFI_KEY\[0\]=''/aWIFI_KEY[0]='${WIFI_PASS}'/" "${MOUNT_DIR}/dietpi-wifi.txt"

# Inject the Automation_Custom_Script.sh directly into the boot partition.
cp "${ROOT_DIR}/os/setup.sh" "$MOUNT_DIR/Automation_Custom_Script.sh"

# Make the injected script executable.
sudo chmod +x "${MOUNT_DIR}/Automation_Custom_Script.sh"

# Last, unmount and clean up.
echo "Unmounting drive..."
sudo umount "${MOUNT_DIR}"
rm -rf "${MOUNT_DIR}"

echo ""
echo "=============================================="
echo " SUCCESS! The SD card is fully provisioned.   "
echo " You can now plug it into the Raspberry Pi,   "
echo " plug the Pi into power, and wait ~10 mins    "
echo " for it to silently install everything.       "
echo "=============================================="