#!/bin/bash
# ---------------------------------------------------------
# Airspace Monitor Flash Script for Raspberry Pi
#
# This script flashes an SD card with the OS and tools to
# run Airspace Monitor on any Raspberry Pi.
#
# Be careful of which SD card you select!!!
# ---------------------------------------------------------

CURRENT_DIR="$(readlink -f "$(dirname "${BASH_SOURCE[0]}")")"
source "${CURRENT_DIR}/variables.sh"
source "${CURRENT_DIR}/common.sh"

echo "=============================================="
echo "  Airspace Monitor SD Card Provisioner        "
echo "=============================================="
echo ""

# Check for required host tools. lsblk/diskutil is handled per-platform below.
require_tools curl xz dd mount umount awk mktemp tr

# Download and cache the DietPi image.
fetch_image
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

# A typo here costs the user a disk, so check what we were handed before we
# offer to erase it.
if [ ! -b "${TARGET_DRIVE}" ]; then
    echo "Error: ${TARGET_DRIVE} is not a block device. Aborting."
    exit 1
fi

read -p "WARNING: ALL DATA ON ${TARGET_DRIVE} WILL BE DESTROYED. Type 'YES' to proceed: " CONFIRM
if [ "${CONFIRM}" != "YES" ]; then
    echo "Airspace Monitor will not be installed. Aborting."
    exit 1
fi
echo ""

# Gather everything the headless first boot needs.
read_install_mode
read_location_hints
read_network_credentials
read_appliance_settings

# Prompt the user to install.
echo "============================================================"
echo "Ready to Flash Airspace Monitor"
echo ""
echo "Your Selections:"
echo "Image     - ${OS_CACHE_DIR}/${IMG_NAME}"
echo "Drive     - ${TARGET_DRIVE}"
if [ "${NET_MODE}" = "ethernet" ]; then
    echo "Network   - wired Ethernet"
else
    echo "Network   - Wi-Fi '${WIFI_SSID}' (${WIFI_COUNTRY:-image default country})"
fi
echo "Hostname  - ${PI_HOSTNAME}"
echo "Time zone - ${PI_TIMEZONE}"
echo "Position  - ${HOME_LAT}, ${HOME_LON}"
if [ "${INSTALL_MODE}" = "bare" ]; then
    echo "Install   - BARE: nothing of ours runs on first boot"
else
    echo "Install   - automated on first boot (30-60 minutes)"
fi
echo "============================================================"

read -p "Do these settings look correct? Type 'YES' to proceed: " CONFIRM
if [ "${CONFIRM}" != "YES" ]; then
    echo "Airspace Monitor will not be installed. Aborting."
    exit 1
fi
echo ""

# Desktops mount a card as soon as it is inserted. Writing the whole device
# underneath a mounted filesystem corrupts the result, so clear them first.
echo "Unmounting any existing partitions on ${TARGET_DRIVE}..."
if command -v lsblk &> /dev/null; then
    while read -r mounted; do
        [ -n "${mounted}" ] || continue
        echo "  unmounting ${mounted}"
        sudo umount "${mounted}" || true
    done < <(lsblk -ln -o MOUNTPOINT "${TARGET_DRIVE}" 2>/dev/null | grep -v '^$')
else
    diskutil unmountDisk "${TARGET_DRIVE}" || true
fi

# Flash the image to the SD card.
echo "Flashing image to ${TARGET_DRIVE}... (This may take a few minutes. You may be prompted for your sudo password)"
if ! sudo dd if="${OS_CACHE_DIR}/${IMG_NAME}" of="${TARGET_DRIVE}" bs=4M status=progress conv=fsync; then
    echo "Error: Writing the image to ${TARGET_DRIVE} failed. The card is not usable as it stands."
    exit 1
fi
echo "Syncing filesystem..."
sync

# The kernel is still holding the partition table from before the write.
# Without a re-read, the boot partition we are about to mount is the old one.
echo "Re-reading the partition table..."
if command -v partprobe &> /dev/null; then
    sudo partprobe "${TARGET_DRIVE}" || true
elif command -v blockdev &> /dev/null; then
    sudo blockdev --rereadpt "${TARGET_DRIVE}" || true
fi
command -v udevadm &> /dev/null && sudo udevadm settle || true

# Mount the boot partition to inject configurations.
echo "Mounting boot partition to inject Wi-Fi and automation scripts..."
MOUNT_DIR="$(mktemp -d -t dietpi_boot_XXXXXX)"

# Determine the partition name based on standard naming conventions.
if [[ "${TARGET_DRIVE}" == *"mmcblk"* ]] || [[ "${TARGET_DRIVE}" == *"nvme"* ]]; then
    PARTITION="${TARGET_DRIVE}p1"
elif [[ "${TARGET_DRIVE}" == *"disk"* ]]; then
    PARTITION="${TARGET_DRIVE}s1"
else
    PARTITION="${TARGET_DRIVE}1"
fi

# Leaving a card half-provisioned is worse than failing loudly, so the mount
# and temp directory are cleaned up however we leave from here.
# umount is attempted unconditionally rather than gated on mountpoint(1),
# which does not exist on macOS: a missing check there would leave the card
# mounted and half-written.
cleanup() {
    sudo umount "${MOUNT_DIR}" 2>/dev/null || true
    rmdir "${MOUNT_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for the partition node to appear: udev can take a moment after a write.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -b "${PARTITION}" ] && break
    sleep 1
done

if [ ! -b "${PARTITION}" ]; then
    echo "Error: Boot partition ${PARTITION} never appeared. You may need to re-insert the card and inject the files manually."
    exit 1
fi

if ! sudo mount "${PARTITION}" "${MOUNT_DIR}"; then
    echo "Error: Failed to mount ${PARTITION}. You may need to manually inject the files."
    exit 1
fi

# Write our automation settings, Wi-Fi details and first-boot script.
inject_boot_config "${MOUNT_DIR}"

# Last, flush and unmount. cleanup() above handles the rest.
echo "Unmounting drive..."
sync

echo ""
echo "=============================================="
echo " SUCCESS! The SD card is fully provisioned.   "
echo " You can now plug it into the Raspberry Pi,   "
echo " plug the Pi into power, and wait ~10 mins    "
echo " for it to silently install everything.       "
echo "=============================================="
