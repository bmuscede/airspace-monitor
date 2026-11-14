#!/bin/bash
# ---------------------------------------------------------
# OS Automation Script for Airspace Monitor
# This must be copied to the boot partition of DietPi.
# ---------------------------------------------------------

echo "Starting Airspace Monitor automated setup..."

# Note: Please update the GITHUB_REPO variable if you are not bmuscede.
GITHUB_REPO="https://github.com/bmuscede/airspace-monitor.git"
INSTALL_DIR="/opt/airspace-monitor"
RTL_LIB_DIR="/opt/rtl-libs"

# Update package list and install system dependencies.
apt-get update
apt-get install -y gcc-aarch64-linux-gnu g++-aarch64-linux-gnu build-essential git python3 python3-pip python3-venv python3-dev i2c-tools python3-smbus spi-tools nodejs npm swig liblgpio-dev python3-tk libcairo2

# Enable I2C and SPI on the Raspberry Pi hardware level
sed -i 's/#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' /boot/config.txt
sed -i 's/#dtparam=spi=on/dtparam=spi=on/' /boot/config.txt

# Ensure we have Debian packages setup for RTL v4
echo "Setting up ADS-B Libraries (RTL v4)..."
apt-get update
apt-get install -y libusb-1.0-0-dev git cmake build-essential pkg-config build-essential
apt-get install -y debhelper
mkdir -p "${RTL_LIB_DIR}"

cd "${RTL_LIB_DIR}"
git clone https://github.com/osmocom/rtl-sdr
cd rtl-sdr
dpkg-buildpackage -b --no-sign
cd ..
dpkg -i librtlsdr0_*.deb
dpkg -i librtlsdr-dev_*.deb
dpkg -i rtl-sdr_*.deb

# Install the ADS-B Decoder (readsb)
echo "Installing readsb (ADS-B Decoder)..."
bash -c "$(wget -q -O - https://github.com/wiedehopf/adsb-scripts/raw/master/readsb-install.sh)"

# Clone the project repository
echo "Cloning repository from $GITHUB_REPO..."

# Remove the directory if it somehow already exists, then clone
rm -rf $INSTALL_DIR
git clone $GITHUB_REPO $INSTALL_DIR

# Set up the Python Backend (monitor-service)
echo "Setting up Python environment..."
cd $INSTALL_DIR/monitor-service
python3 -m venv venv
$INSTALL_DIR/monitor-service/venv/bin/pip install --upgrade pip

# Install universal API dependencies, followed by hardware-specific ones
if [ -f "requirements.txt" ]; then
    $INSTALL_DIR/monitor-service/venv/bin/pip install -r requirements.txt
fi

if [ -f "rpi.requirements.txt" ]; then
    $INSTALL_DIR/monitor-service/venv/bin/pip install -r rpi.requirements.txt
fi

# Set up the React Dashboard (monitor-dashboard)
echo "Setting up Monitor Dashboard Environment..."
cd $INSTALL_DIR/monitor-dashboard
npm install

# ---------------------------------------------------------
# Live log directory (tmpfs)
#
# The service writes two logs: a high-volume INFO log that the dashboard tails,
# and a small WARNING+ log kept for post-mortem diagnosis. Only the second one
# belongs on the SD card. The first goes to RAM, where writes are free.
#
# DietPi's RAMlog usually already mounts /var/log as tmpfs, so check rather than
# assume. We still give ourselves a dedicated mount with an explicit size cap:
# RAMlog defaults to 20MB for the whole of /var/log, and our rotation budget
# (5MB x 2 backups) would come close to filling it on its own.
# ---------------------------------------------------------
echo "Setting up tmpfs for live logs..."
LIVE_LOG_DIR="/var/log/airspace-monitor"

PARENT_FSTYPE="$(findmnt -n -o FSTYPE --target /var/log 2>/dev/null)"
if [ "$PARENT_FSTYPE" = "tmpfs" ]; then
    echo "Verified: /var/log is already tmpfs (DietPi RAMlog)."
else
    echo "Note: /var/log is '$PARENT_FSTYPE', not tmpfs. Mounting our own."
fi

mkdir -p "${LIVE_LOG_DIR}"
if ! grep -q "${LIVE_LOG_DIR}" /etc/fstab; then
    echo "tmpfs ${LIVE_LOG_DIR} tmpfs defaults,noatime,nosuid,nodev,size=32M,mode=0755 0 0" >> /etc/fstab
fi
mountpoint -q "${LIVE_LOG_DIR}" || mount "${LIVE_LOG_DIR}"

# Create the Python Backend Service
echo "Creating Monitor Service Environment..."
cat << 'EOF' > /etc/systemd/system/airspace-monitor-service.service
[Unit]
Description=Airspace Monitor Python Backend
After=network.target readsb.service

[Service]
ExecStartPre=/bin/mkdir -p /var/log/airspace-monitor
ExecStart=/opt/airspace-monitor/monitor-service/venv/bin/python main.py --live_log_dir /var/log/airspace-monitor --log_dir /opt/airspace-monitor/monitor-service
WorkingDirectory=/opt/airspace-monitor/monitor-service
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

# systemctl stop/restart sends SIGTERM, which the controller catches to close
# out open contacts and flush the history database before exiting. That drain
# is bounded by SHUTDOWN_TIMEOUT_SECONDS (10s) in controller.py plus at most
# one 2s hardware cycle, so 30s is comfortable headroom. Do not drop this below
# ~15s or systemd will SIGKILL mid-flush and the contacts will come back as
# closed = 0 orphans on the next start.
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create the Monitor Dashboard Service
# TODO: Currently runs as dev.
echo "Creating Monitor Dashboard systemd service..."
cat << 'EOF' > /etc/systemd/system/airspace-monitor-dashboard.service
[Unit]
Description=Airspace Monitor React Dashboard
After=network.target airspace-monitor-service.service

[Service]
ExecStart=/usr/bin/npm run dev -- --host 0.0.0.0
WorkingDirectory=/opt/airspace-monitor/monitor-dashboard
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# Enable and start both services.
systemctl enable airspace-monitor-service.service
systemctl enable airspace-monitor-dashboard.service
systemctl start airspace-monitor-service.service
systemctl start airspace-monitor-dashboard.service

echo "Airspace Monitor setup complete! Rebooting..."
reboot