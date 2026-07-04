#!/bin/bash
# ---------------------------------------------------------
# OS Automation Script for Airspace Monitor
# This must be copied to the boot partition.
# ---------------------------------------------------------

echo "Starting Airspace Monitor automated setup..."

# Update package list and install system dependencies.
# We need Python, pip, git, and hardware buses (I2C/SPI) for the displays
apt-get update
apt-get install -y python3 python3-pip python3-venv git i2c-tools python3-smbus spi-tools

# Enable I2C and SPI on the Raspberry Pi hardware level
# This is required for the Split-flap driver (I2C) and E-Ink (SPI)
sed -i 's/#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' /boot/config.txt
sed -i 's/#dtparam=spi=on/dtparam=spi=on/' /boot/config.txt

# Install the ADS-B Decoder
# We use 'readsb' (a highly optimized, modern fork of dump1090).
# This automated script pulls the software and configures the RTL-SDR.
echo "Installing readsb (ADS-B Decoder)..."
bash -c "$(wget -q -O - https://github.com/wiedehopf/adsb-scripts/raw/master/readsb-install.sh)"

# Set up the project directory and Python virtual environment
echo "Setting up Python environment..."
mkdir -p /opt/airspace-monitor
cd /opt/airspace-monitor

# Create a virtual environment so we don't conflict with system Python
python3 -m venv venv
/opt/airspace-monitor/venv/bin/pip install --upgrade pip

# Install libraries for I2C and common E-Ink dependencies
/opt/airspace-monitor/venv/bin/pip install smbus2 spidev RPi.GPIO Pillow requests

# Create a placeholder for your future Python controller script
cat << 'EOF' > /opt/airspace-monitor/controller.py
import time

def main():
    print("Airspace Monitor controller is running!")
    # Future code: Read JSON from readsb, update E-Ink/Flaps
    while True:
        time.sleep(10)

if __name__ == "__main__":
    main()
EOF

# Create the systemd service to run the Python script automatically on boot
echo "Creating systemd service..."
cat << 'EOF' > /etc/systemd/system/airspace-monitor.service
[Unit]
Description=Airspace Monitor Controller
# Ensure the network and the ADS-B decoder are running first
After=network.target readsb.service

[Service]
ExecStart=/opt/airspace-monitor/venv/bin/python /opt/airspace-monitor/controller.py
WorkingDirectory=/opt/airspace-monitor
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# Enable the service so it starts on every reboot
systemctl enable airspace-monitor.service
systemctl start airspace-monitor.service

echo "Airspace Monitor setup complete! Rebooting..."
reboot