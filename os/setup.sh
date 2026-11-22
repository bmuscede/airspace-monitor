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

# ---------------------------------------------------------
# Nothing here may ever wait for a human.
#
# This runs on first boot with no console reachable inside the case, so a
# prompt is not a question -- it is a hang that looks exactly like a dead
# board. apt can stop on a conffile prompt, and git will sit forever asking
# for credentials if a clone URL is wrong or a repo has gone private.
# ---------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
APT_OPTS=(-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

# This runs unattended on first boot with nobody watching, so every step says
# whether it worked. A failure that scrolls past is a Pi that comes up with no
# display and no clue why.
FAILED_STEPS=()

# ---------------------------------------------------------
# fatal <message>
#
# For the steps there is no point continuing past.
# ---------------------------------------------------------
fatal() {
    log_progress "FATAL: $*"
    log_progress "Airspace Monitor setup cannot continue."
    exit 1
}

# ---------------------------------------------------------
# note_failure <message>
#
# For the steps worth finishing the install without. These
# are collected and reprinted at the end.
# ---------------------------------------------------------
note_failure() {
    log_progress "WARNING: $*"
    FAILED_STEPS+=("$*")
}

# ---------------------------------------------------------
# log_progress <message>
#
# Prints a message and appends it, timestamped, to a log on
# the FAT boot partition.
#
# This install takes the better part of an hour: it builds
# rtl-sdr and readsb from source and runs npm install. Every
# other log it writes lands on ext4, which a Windows or macOS
# machine cannot read. A log on the FAT partition can be read
# by pulling the card and putting it in any laptop, which is
# the only diagnostic left if the board never comes back.
# ---------------------------------------------------------
INSTALL_LOG=""
log_progress() {
    echo "$*"
    [ -n "${INSTALL_LOG}" ] || return 0
    printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%SZ')" "$*" >> "${INSTALL_LOG}" 2>/dev/null
    # FAT has no journal and the board may lose power mid-build, so every line
    # is flushed instead of sitting in cache.
    sync 2>/dev/null || true
}

# ---------------------------------------------------------
# boot_config_path
#
# Where config.txt lives. Trixie and Bookworm mount the FAT
# boot partition at /boot/firmware; older images used /boot.
# Writing to the wrong one silently does nothing, which is
# how SPI ends up disabled and the E-Ink display dead.
# ---------------------------------------------------------
boot_config_path() {
    local candidate
    for candidate in /boot/firmware/config.txt /boot/config.txt; do
        if [ -f "${candidate}" ]; then
            echo "${candidate}"
            return 0
        fi
    done
    return 1
}

# ---------------------------------------------------------
# flash_setting <key>
#
# Reads one value out of airspace-monitor.conf, the file the
# flashing script leaves on the boot partition. The file is
# read rather than sourced, so nothing in it is executed,
# and every value is validated by the caller.
# ---------------------------------------------------------
flash_setting() {
    local key="$1" candidate
    for candidate in /boot/firmware/airspace-monitor.conf /boot/airspace-monitor.conf; do
        if [ -f "${candidate}" ]; then
            sed -n "s/^${key}=\(.*\)$/\1/p" "${candidate}" | head -1
            return 0
        fi
    done
}

# ---------------------------------------------------------
# Open the progress log on the boot partition. Everything
# from here on is recorded somewhere readable without the Pi.
# ---------------------------------------------------------
BOOT_CONFIG_DIR=""
if BOOT_CONFIG_FILE="$(boot_config_path)"; then
    BOOT_CONFIG_DIR="$(dirname "${BOOT_CONFIG_FILE}")"
    if : > "${BOOT_CONFIG_DIR}/airspace-monitor-install.log" 2>/dev/null; then
        INSTALL_LOG="${BOOT_CONFIG_DIR}/airspace-monitor-install.log"
    fi
fi

# ---------------------------------------------------------
# log_power_state <when>
#
# Records whether the board has browned out or been throttled.
#
# A compile is the heaviest sustained load this board ever
# sees, and an RTL-SDR dongle draws a few hundred mA on top.
# A marginal supply or a tired cable shows up here and
# nowhere else: an undervolting Pi corrupts builds, wedges,
# or reboots, all of which look like a broken install from
# the outside. Checked at both ends of the install, because
# a flag that is clear at the start and set at the end points
# squarely at power rather than software.
# ---------------------------------------------------------
log_power_state() {
    local when="$1" raw bits

    if ! command -v vcgencmd &> /dev/null; then
        log_progress "Power (${when}): vcgencmd unavailable, cannot check."
        return 0
    fi

    raw="$(vcgencmd get_throttled 2>/dev/null)"
    bits="${raw#throttled=}"
    if [ -z "${bits}" ] || [ "${bits}" = "${raw}" ]; then
        log_progress "Power (${when}): could not read the throttling flags."
        return 0
    fi

    if [ "${bits}" = "0x0" ]; then
        log_progress "Power (${when}): OK, no undervoltage or throttling (${bits})."
        return 0
    fi

    # Bits 0-3 are happening now, 16-19 have happened since boot.
    local decoded="" value=$(( bits ))
    (( value & 0x1 ))     && decoded="${decoded} undervoltage-now"
    (( value & 0x2 ))     && decoded="${decoded} arm-freq-capped-now"
    (( value & 0x4 ))     && decoded="${decoded} throttled-now"
    (( value & 0x8 ))     && decoded="${decoded} soft-temp-limit-now"
    (( value & 0x10000 )) && decoded="${decoded} undervoltage-has-occurred"
    (( value & 0x20000 )) && decoded="${decoded} arm-freq-capping-has-occurred"
    (( value & 0x40000 )) && decoded="${decoded} throttling-has-occurred"
    (( value & 0x80000 )) && decoded="${decoded} soft-temp-limit-has-occurred"

    log_progress "Power (${when}): ${bits} =>${decoded}"
    if (( value & 0x10001 )); then
        log_progress "  ^ UNDERVOLTAGE. Suspect the supply or the cable feeding the Pi,"
        log_progress "    not the software. A dongle plus a compile is the peak draw this"
        log_progress "    board sees, and a weak cable fails exactly here."
    fi
}

log_progress "=== Airspace Monitor install starting ==="
log_progress "Expect this to take 30-60 minutes: rtl-sdr and readsb are built"
log_progress "from source and the dashboard runs npm install. The board stays"
log_progress "reachable throughout, and reboots once at the end."
log_progress "Board: $(tr -d '\0' < /proc/device-tree/model 2>/dev/null)"
log_progress "Disk : $(df -h / | awk 'NR==2 {print $4" free of "$2}')"
log_power_state "at start"

# ---------------------------------------------------------
# set_boot_param <file> <key> <value>
#
# Sets "key=value" in config.txt, whether the line is
# already set, commented out, or absent. The shipped image
# has these commented and set to "off", so a plain
# uncommenting sed finds nothing to do.
# ---------------------------------------------------------
set_boot_param() {
    local file="$1" key="$2" value="$3"

    # Drop every existing form of the line, commented or not, then append the
    # one we want. Appending is safe: config.txt applies the last value, and
    # there are no conditional [sections] after the point we add to.
    sed -i -E "/^[[:blank:]]*#?[[:blank:]]*${key}=/d" "${file}"
    echo "${key}=${value}" >> "${file}"
}

# Update package list and install system dependencies.
# Logged, because this takes several minutes and an unlabelled gap at the top
# of the log is indistinguishable from a hang here.
log_progress "[0/9] Updating apt and installing system dependencies..."
apt-get update < /dev/null
# avahi-daemon and libnss-mdns are what make the hostname set at flash time
# reachable as <hostname>.local. Neither ships in the DietPi image, so without
# them the hostname is only visible to whoever reads the router's lease table.
# wget and ca-certificates are listed rather than assumed: the readsb installer
# is fetched with wget over HTTPS, and a missing one of those made that step
# fail invisibly.
# python3-gpiozero and python3-lgpio are apt packages on purpose, not pip ones.
# waveshare-epaper's Raspberry Pi backend runs "import gpiozero" the moment the
# panel module is imported, but its package metadata declares only RPi.GPIO and
# spidev -- so pip installs it happily and it dies at run time. gpiozero in turn
# needs a pin factory, which on Trixie is lgpio, and installing lgpio from pip
# means compiling its C library on the board. Debian ships both ready built. The
# venv further down is created with --system-site-packages so it can see them.
apt-get install "${APT_OPTS[@]}" gcc-aarch64-linux-gnu g++-aarch64-linux-gnu build-essential git wget ca-certificates python3 python3-pip python3-venv python3-dev i2c-tools python3-smbus spi-tools nodejs npm swig liblgpio-dev python3-lgpio python3-gpiozero python3-tk libcairo2 avahi-daemon libnss-mdns \
    || fatal "Could not install system dependencies."

# --now matters: "enable" alone only arms it for the next boot, which would
# leave <hostname>.local unresolvable for the whole install -- exactly when
# someone is trying to find the board to see how it is getting on.
systemctl enable --now avahi-daemon &> /dev/null \
    || note_failure "Could not start avahi-daemon; <hostname>.local will not resolve."

# ---------------------------------------------------------
# Enable I2C and SPI at the hardware level.
#
# The E-Ink panel is driven over SPI, so without this the display driver comes
# up, finds no /dev/spidev*, and the Pi shows nothing. These only take effect
# after the reboot at the end of this script.
# ---------------------------------------------------------
log_progress "[1/9] Enabling I2C and SPI..."
BOOT_CONFIG="$(boot_config_path)"
if [ -z "${BOOT_CONFIG}" ]; then
    note_failure "Could not find config.txt in /boot/firmware or /boot. I2C and SPI are NOT enabled, so the E-Ink display will not work."
else
    echo "Using boot config: ${BOOT_CONFIG}"
    set_boot_param "${BOOT_CONFIG}" "dtparam=i2c_arm" "on"
    set_boot_param "${BOOT_CONFIG}" "dtparam=spi" "on"

    # Verify, because this is the step whose failure is hardest to diagnose
    # later: a silently-unmodified config.txt looks identical to a wiring fault.
    if grep -qE '^dtparam=spi=on' "${BOOT_CONFIG}" && grep -qE '^dtparam=i2c_arm=on' "${BOOT_CONFIG}"; then
        echo "Verified: I2C and SPI will be enabled after reboot."
    else
        note_failure "Wrote to ${BOOT_CONFIG} but the dtparam lines are not there. The E-Ink display will not work."
    fi
fi

# Ensure we have Debian packages setup for RTL v4
log_progress "[2/9] Building RTL-SDR v4 libraries from source (slow)..."
apt-get update < /dev/null
apt-get install "${APT_OPTS[@]}" libusb-1.0-0-dev git cmake build-essential pkg-config \
    || note_failure "Could not install RTL-SDR build dependencies."
apt-get install "${APT_OPTS[@]}" debhelper || note_failure "Could not install debhelper."
mkdir -p "${RTL_LIB_DIR}"

cd "${RTL_LIB_DIR}" || fatal "Could not enter ${RTL_LIB_DIR}."

# Start from a clean tree so re-running this script does not fail on an
# existing clone.
rm -rf "${RTL_LIB_DIR}/rtl-sdr"
if git clone https://github.com/osmocom/rtl-sdr; then
    cd rtl-sdr || fatal "Could not enter the rtl-sdr source tree."
    dpkg-buildpackage -b --no-sign < /dev/null || note_failure "Could not build the RTL-SDR packages."
    cd ..

    # dpkg alone will not pull dependencies, so apt settles up after.
    dpkg -i librtlsdr0_*.deb librtlsdr-dev_*.deb rtl-sdr_*.deb \
        || apt-get -f install "${APT_OPTS[@]}" \
        || note_failure "Could not install the RTL-SDR packages."
else
    note_failure "Could not clone the RTL-SDR source. The ADS-B receiver may not work."
fi

# Install the ADS-B Decoder (readsb)
# This writes /run/readsb/aircraft.json, which is the feed the monitor service
# reads. Its installer sets up and enables the readsb service itself.
log_progress "[3/9] Installing readsb ADS-B decoder (slow, builds from source)..."

# Downloaded to a file and checked before being run, rather than piped straight
# into bash. A failed download there produces an empty string, and "bash -c """
# exits 0 -- so a readsb that was never installed looked like a clean success.
READSB_INSTALLER="$(mktemp)"
if wget -q -O "${READSB_INSTALLER}" \
        https://github.com/wiedehopf/adsb-scripts/raw/master/readsb-install.sh \
        && [ -s "${READSB_INSTALLER}" ]; then

    # Two guards around a third-party script, because an earlier install
    # stopped dead on this line and left no trace of why:
    #
    #   < /dev/null  anything that reads stdin gets EOF instead of waiting
    #                forever. There is no terminal here to answer a prompt,
    #                so a question is not a question -- it is a hang.
    #   timeout      turns a hang into a logged failure. The install carries
    #                on without readsb, which is far better than stopping
    #                here and leaving nothing installed at all.
    READSB_TIMEOUT=1800
    timeout "${READSB_TIMEOUT}" bash "${READSB_INSTALLER}" < /dev/null
    READSB_STATUS=$?

    if [ "${READSB_STATUS}" -eq 124 ]; then
        note_failure "The readsb installer was still running after ${READSB_TIMEOUT}s and was stopped. It most likely stalled waiting for input or on the network. Run it by hand: bash /tmp/readsb-install.sh"
        cp "${READSB_INSTALLER}" /tmp/readsb-install.sh 2>/dev/null || true
    elif [ "${READSB_STATUS}" -ne 0 ]; then
        note_failure "The readsb installer exited ${READSB_STATUS}. The service will start but report no aircraft."
    else
        log_progress "readsb installer finished."
    fi
else
    note_failure "Could not download the readsb installer. The service will start but report no aircraft."
fi
rm -f "${READSB_INSTALLER}"

# Clone the project repository
log_progress "[4/9] Cloning repository from $GITHUB_REPO..."
log_progress "Disk free before clone: $(df -h / | awk 'NR==2 {print $4" of "$2" ("$5" used)"}')"

# Retried rather than fatal on the first failure: this is the step most exposed
# to a transient DNS or Wi-Fi hiccup, and giving up here means a card that has
# to be written again from scratch.
CLONE_ATTEMPT=1
while :; do
    rm -rf "${INSTALL_DIR}"
    git clone "${GITHUB_REPO}" "${INSTALL_DIR}" && break

    if [ "${CLONE_ATTEMPT}" -ge 3 ]; then
        log_progress "Clone failed ${CLONE_ATTEMPT} times."
        log_progress "  Check from the Pi: ping -c1 github.com, and"
        log_progress "  git clone ${GITHUB_REPO} /tmp/t"
        log_progress "  The repository must be reachable without credentials."
        fatal "Could not clone ${GITHUB_REPO}."
    fi

    CLONE_ATTEMPT=$((CLONE_ATTEMPT + 1))
    log_progress "Clone failed; retrying in 15s (attempt ${CLONE_ATTEMPT} of 3)..."
    sleep 15
done

# Set up the Python Backend (monitor-service)
log_progress "[5/9] Setting up Python environment..."
cd $INSTALL_DIR/monitor-service || fatal "Could not enter the monitor-service directory."
# --system-site-packages is load bearing. gpiozero and lgpio come from apt, and
# a plain venv cannot see apt-installed modules at all, so the E-Ink driver
# would import, fail on gpiozero, and leave the panel blank.
python3 -m venv --system-site-packages venv \
    || fatal "Could not create the Python virtual environment."

# A venv built before this flag existed keeps its old pyvenv.cfg, and re-running
# "python3 -m venv" over it is not guaranteed to rewrite the setting. Correct it
# in place rather than deleting an environment somebody may have fixed by hand.
if [ -f venv/pyvenv.cfg ] && grep -q "include-system-site-packages = false" venv/pyvenv.cfg; then
    sed -i "s/include-system-site-packages = false/include-system-site-packages = true/" venv/pyvenv.cfg \
        && log_progress "  Existing venv could not see system packages; corrected."
fi

$INSTALL_DIR/monitor-service/venv/bin/pip install --upgrade pip \
    || note_failure "Could not upgrade pip."

# Install universal API dependencies, followed by hardware-specific ones
if [ -f "requirements.txt" ]; then
    $INSTALL_DIR/monitor-service/venv/bin/pip install -r requirements.txt \
        || fatal "Could not install the monitor service requirements."
fi

if [ -f "rpi.requirements.txt" ]; then
    # This is where the Waveshare E-Ink and SPI libraries come from. gpiozero
    # and lgpio are deliberately not listed in there: they are apt packages,
    # and a pip copy inside the venv would shadow the working system one.
    $INSTALL_DIR/monitor-service/venv/bin/pip install -r rpi.requirements.txt \
        || note_failure "Could not install the Raspberry Pi hardware requirements. The displays will not work."
fi

# ---------------------------------------------------------
# Prove the display stack actually imports.
#
# Every failure here is silent twice over: pip reports success, and then
# EInkDisplay catches the import error, logs a single line, sets its panel to
# None and carries on serving a dashboard that drives nothing. A missing
# gpiozero looks exactly like a dead panel. Importing the modules now puts the
# answer in the install log instead of in a service log nobody is reading.
#
# gpiozero is imported but not exercised on purpose: constructing a pin claims
# GPIO lines that the service wants a few minutes later.
for module in spidev gpiozero lgpio epaper PIL; do
    if $INSTALL_DIR/monitor-service/venv/bin/python -c "import ${module}" 2> /dev/null; then
        log_progress "  python: ${module} imports OK"
    else
        note_failure "python: ${module} will not import inside the venv. The E-Ink display will stay blank."
    fi
done

# ---------------------------------------------------------
# Seed the receiver position.
#
# The service needs its own latitude and longitude to work out which aircraft
# are overhead, and it is the closest one that gets the display. The defaults
# are 0.0/0.0 -- a point in the Atlantic -- so without this the appliance comes
# up tracking nothing until someone opens the dashboard. The flashing script
# collected the position; this is the first point at which there is a
# config.json to put it in.
#
# Only these two keys are written. ConfigManager merges the file over its
# defaults object by object, so everything else still comes from the defaults.
# ---------------------------------------------------------
log_progress "[6/9] Seeding receiver location..."
HOME_LAT="$(flash_setting HOME_LAT)"
HOME_LON="$(flash_setting HOME_LON)"

# Validated here too, not just at flash time: this is a file on a partition
# anyone can edit, and it is about to be written into JSON.
if [[ "${HOME_LAT}" =~ ^-?[0-9]{1,2}(\.[0-9]+)?$ ]] && [[ "${HOME_LON}" =~ ^-?[0-9]{1,3}(\.[0-9]+)?$ ]]; then
    if [ -f "${INSTALL_DIR}/monitor-service/config.json" ]; then
        echo "config.json already exists; leaving the position alone."
    else
        cat << EOF > "${INSTALL_DIR}/monitor-service/config.json"
{
    "radar": {
        "home_lat": ${HOME_LAT},
        "home_lon": ${HOME_LON}
    }
}
EOF
        echo "Receiver position set to ${HOME_LAT}, ${HOME_LON}."
    fi

    # readsb uses the receiver location for range filtering and for decoding
    # surface positions. The service does its own distance maths from
    # config.json, so this is a bonus rather than a requirement -- and the file
    # belongs to the readsb installer, so only a recognisable line is touched.
    if [ -f /etc/default/readsb ] && grep -q '^[[:blank:]]*DECODER_OPTIONS=' /etc/default/readsb; then
        # Drop any location this line already carries, then add ours, so a
        # re-run leaves one pair rather than appending another.
        sed -i -E "/^[[:blank:]]*DECODER_OPTIONS=/ s|--la(t)?[[:blank:]]+-?[0-9.]+||g; \
                   /^[[:blank:]]*DECODER_OPTIONS=/ s|--lon[[:blank:]]+-?[0-9.]+||g" \
            /etc/default/readsb
        sed -i -E "/^[[:blank:]]*DECODER_OPTIONS=/ s|\"[[:blank:]]*$| --lat ${HOME_LAT} --lon ${HOME_LON}\"|" \
            /etc/default/readsb
        # Collapse the gaps the removal above leaves, so the file stays
        # readable for whoever opens it next.
        sed -i -E "/^[[:blank:]]*DECODER_OPTIONS=/ s|[[:blank:]]{2,}| |g" /etc/default/readsb
        if grep -q -- "--lat ${HOME_LAT}" /etc/default/readsb; then
            echo "Told readsb where the receiver is."
            systemctl restart readsb &> /dev/null || true
        else
            note_failure "Could not set the receiver location in /etc/default/readsb."
        fi
    else
        note_failure "/etc/default/readsb has no DECODER_OPTIONS line; readsb was not told the receiver location."
    fi
else
    note_failure "No usable receiver position was flashed to the card. Set it in the dashboard, or the display will track nothing."
fi

# Set up the React Dashboard (monitor-dashboard)
log_progress "[7/9] Installing dashboard dependencies with npm (slow)..."
cd $INSTALL_DIR/monitor-dashboard || fatal "Could not enter the monitor-dashboard directory."
timeout 2700 npm install --no-fund --no-audit < /dev/null || note_failure "Could not install the dashboard dependencies. The dashboard will not start."

# ---------------------------------------------------------
# Live log directory (tmpfs)
#
# The service writes two logs: a high-volume INFO log that the dashboard tails,
# and a small WARNING+ log kept for post-mortem diagnosis. Only the second one
# belongs on the SD card. The first goes to RAM, where writes are free.
#
# DietPi's RAMlog usually already mounts /var/log as tmpfs, so check rather than
# assume. We still give ourselves a dedicated mount with an explicit size cap:
# RAMlog is sized by AUTO_SETUP_RAMLOG_MAXSIZE in dietpi.txt, 50MiB on the
# images we flash, shared by the whole of /var/log. Our rotation budget
# (5MB x 2 backups) would take a fifth of that on its own, so we take a
# dedicated 32MiB mount rather than competing for it.
# ---------------------------------------------------------
log_progress "[8/9] Setting up tmpfs for live logs..."
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
mountpoint -q "${LIVE_LOG_DIR}" || mount "${LIVE_LOG_DIR}" \
    || note_failure "Could not mount the live log tmpfs. Logs will fall back to the SD card."

# Create the Python Backend Service
log_progress "[9/9] Registering systemd services..."
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

# Pick up the two unit files we just wrote before enabling them.
systemctl daemon-reload || note_failure "systemctl daemon-reload failed."

# Enable and start both services.
systemctl enable airspace-monitor-service.service \
    || note_failure "Could not enable the monitor service."
systemctl enable airspace-monitor-dashboard.service \
    || note_failure "Could not enable the dashboard service."
systemctl start airspace-monitor-service.service \
    || note_failure "Could not start the monitor service."
systemctl start airspace-monitor-dashboard.service \
    || note_failure "Could not start the dashboard service."

# readsb is the feed everything else depends on. Its own installer enables it,
# so this only reports what we ended up with.
if systemctl is-enabled readsb.service &> /dev/null; then
    log_progress "Verified: readsb is enabled and will start on boot."
else
    note_failure "readsb is not enabled. The service will report no aircraft until it is."
fi

# ---------------------------------------------------------
# Report what did not work, so a first boot that half-failed says so instead
# of looking identical to a clean one.
# ---------------------------------------------------------
log_progress ""
log_progress "=============================================="
if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
    log_progress " Airspace Monitor setup complete!"
else
    log_progress " Airspace Monitor setup finished with ${#FAILED_STEPS[@]} problem(s):"
    for step in "${FAILED_STEPS[@]}"; do
        log_progress "   - ${step}"
    done
fi

# The same check as at the start. A flag that was clear then and is set now
# means the board browned out under the build, which is a supply or cable
# fault rather than anything in this script.
log_progress ""
log_power_state "at end"

# The kernel's own account, which survives in the log even though the console
# this would normally be read on is not reachable inside the case.
UNDERVOLT_LINES="$(dmesg 2>/dev/null | grep -ci 'voltage' || true)"
if [ "${UNDERVOLT_LINES:-0}" -gt 0 ]; then
    log_progress "Kernel logged ${UNDERVOLT_LINES} voltage message(s) this boot:"
    dmesg 2>/dev/null | grep -i 'voltage' | tail -5 | while read -r line; do
        log_progress "  ${line}"
    done
fi

# Where to reach it, recorded on the boot partition so it can be read from the
# card if the board cannot be found on the network.
log_progress ""
log_progress " Hostname : $(hostname 2>/dev/null)"
log_progress " Addresses: $(hostname -I 2>/dev/null)"
log_progress " Dashboard: http://$(hostname 2>/dev/null).local:5173"
log_progress ""
log_progress " Rebooting now to apply the I2C/SPI settings."
log_progress " This is the only reboot; it should be back in under a minute."
log_progress "=============================================="

# Make sure the log is on the card before the reboot takes the filesystem down.
sync
reboot
