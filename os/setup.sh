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
apt-get install -y gcc-aarch64-linux-gnu g++-aarch64-linux-gnu build-essential git python3 python3-pip python3-venv python3-dev i2c-tools python3-smbus spi-tools nodejs npm swig liblgpio-dev

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

# Create the Python Backend Service
echo "Creating Monitor Service Environment..."
cat << 'EOF' > /etc/systemd/system/airspace-monitor-service.service
[Unit]
Description=Airspace Monitor Python Backend
After=network.target readsb.service

[Service]
ExecStart=/opt/airspace-monitor/monitor-service/venv/bin/python main.py
WorkingDirectory=/opt/airspace-monitor/monitor-service
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

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