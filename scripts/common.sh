#!/bin/bash
# ---------------------------------------------------------
# Shared helpers for the flashing scripts.
#
# flash.sh and flash-windows.sh do the same two jobs: fetch
# the DietPi image, then write our automation and Wi-Fi
# settings into its boot partition. Only the way the card is
# written differs. Both halves live here so the two paths
# cannot drift apart.
# ---------------------------------------------------------

# Writes to the boot partition need root on Linux, where the partition is
# mounted by sudo. On Windows the drive letter is already writable, so the
# caller sets SUDO="" and the same code serves both.
SUDO="${SUDO-sudo}"

# ---------------------------------------------------------
# require_tools <tool>...
#
# Fails with a readable message if any tool is missing.
# ---------------------------------------------------------
require_tools() {
    local tool missing=0
    for tool in "$@"; do
        if ! command -v "${tool}" &> /dev/null; then
            echo "Error: Required tool '${tool}' is not installed. Please install it and try again."
            missing=1
        fi
    done
    [ "${missing}" -eq 0 ] || exit 1
}

# ---------------------------------------------------------
# fetch_image
#
# Downloads and extracts the DietPi image into OS_CACHE_DIR,
# reusing whatever is already cached. Leaves the extracted
# image at ${OS_CACHE_DIR}/${IMG_NAME}.
# ---------------------------------------------------------
fetch_image() {
    local archive="${OS_CACHE_DIR}/${ARCHIVE_NAME}"
    local image="${OS_CACHE_DIR}/${IMG_NAME}"

    if [ ! -f "${archive}" ]; then
        echo "Downloading DietPi OS archive..."
        mkdir -p "${OS_CACHE_DIR}"

        # Download beside the target then move into place, so an interrupted
        # download is never mistaken for a cached one on the next run.
        if ! curl -fL -o "${archive}.part" "${IMAGE_URL}"; then
            rm -f "${archive}.part"
            echo "Error: Could not download DietPi to ${archive}. Please try again later."
            exit 1
        fi
        mv "${archive}.part" "${archive}"
        echo "Using DietPi OS archive: ${ARCHIVE_NAME}"
    else
        echo "Using cached DietPi OS archive: ${ARCHIVE_NAME}"
    fi

    if [ ! -f "${image}" ]; then
        echo "Extracting DietPi OS image..."
        if ! xz -d -k "${archive}"; then
            echo "Error: Could not extract DietPi archive. Please try again later or manually extract it."
            exit 1
        fi
    fi

    # xz names its output after the archive. If that is not where we expect the
    # image to be, stop now rather than handing a missing path to dd.
    if [ ! -f "${image}" ]; then
        echo "Error: Expected the extracted image at ${image}, but it is not there."
        exit 1
    fi
}

# ---------------------------------------------------------
# Validators for the values that end up in config files.
#
# The geolocation lookup below is untrusted network input,
# so everything it suggests is checked before it is offered
# as a default, and again before it is written.
# ---------------------------------------------------------
is_latitude() {
    [[ "$1" =~ ^-?[0-9]{1,2}(\.[0-9]+)?$ ]] \
        && awk -v v="$1" 'BEGIN { exit !(v >= -90 && v <= 90) }'
}

is_longitude() {
    [[ "$1" =~ ^-?[0-9]{1,3}(\.[0-9]+)?$ ]] \
        && awk -v v="$1" 'BEGIN { exit !(v >= -180 && v <= 180) }'
}

is_timezone() {
    # "UTC", "America/Toronto", "America/Argentina/Buenos_Aires".
    [[ "$1" =~ ^[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9_+-]+){0,2}$ ]]
}

is_country_code() {
    [[ "$1" =~ ^[A-Z]{2}$ ]]
}

is_hostname() {
    # A DNS label: letters, digits and hyphens, not starting or ending with one.
    [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$ ]]
}

# ---------------------------------------------------------
# json_string <json> <key>
#
# Pulls one string value out of a flat JSON object. Enough
# for the geolocation response and avoids depending on jq,
# which is not installed by default anywhere we run.
# ---------------------------------------------------------
json_string() {
    printf '%s' "$1" \
        | grep -o "\"$2\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
        | head -1 \
        | sed 's/.*:[[:space:]]*"//; s/"$//'
}

# ---------------------------------------------------------
# read_location_hints
#
# Optionally asks ipinfo.io where this machine is, to
# prefill the receiver position, time zone and Wi-Fi country
# code. Sets GEO_LAT, GEO_LON, GEO_TZ and GEO_COUNTRY, all
# empty when declined or unusable.
#
# Opt-in, and off unless asked for: it tells a third party
# this machine's IP address, which is roughly where the
# user lives. Every value it returns is only ever a default
# the user still confirms.
# ---------------------------------------------------------
read_location_hints() {
    GEO_LAT=""; GEO_LON=""; GEO_TZ=""; GEO_COUNTRY=""

    echo "The receiver needs its own latitude and longitude to work out which"
    echo "aircraft are overhead. These can be looked up approximately from this"
    echo "machine's IP address, which means telling ipinfo.io your IP address."
    echo "Whatever it returns is only a starting point you confirm below."
    echo ""
    read -p "Look up an approximate location from your IP address? [y/N]: " DO_LOOKUP
    echo ""

    case "${DO_LOOKUP}" in
        [Yy]*) ;;
        *) return 0 ;;
    esac

    if ! command -v curl &> /dev/null; then
        echo "Note: curl is not available, so the lookup was skipped."
        return 0
    fi

    local json loc lat lon tz country
    if ! json="$(curl -fsS --max-time 10 https://ipinfo.io/json 2>/dev/null)"; then
        echo "Note: the location lookup failed. Enter the position by hand below."
        return 0
    fi

    loc="$(json_string "${json}" loc)"
    lat="${loc%%,*}"
    lon="${loc##*,}"
    tz="$(json_string "${json}" timezone)"
    country="$(json_string "${json}" country)"

    # Nothing is adopted unless it passes, so a garbled or hostile response
    # just means the user types the values themselves.
    if [ -n "${lat}" ] && [ "${lat}" != "${loc}" ] && is_latitude "${lat}" && is_longitude "${lon}"; then
        GEO_LAT="${lat}"
        GEO_LON="${lon}"
    fi
    is_timezone "${tz}" && GEO_TZ="${tz}"
    is_country_code "${country}" && GEO_COUNTRY="${country}"

    if [ -n "${GEO_LAT}" ]; then
        local city region
        city="$(json_string "${json}" city)"
        region="$(json_string "${json}" region)"
        echo "Looked up: ${GEO_LAT}, ${GEO_LON}${city:+ (${city}${region:+, ${region}})}"
        echo ""
        echo "IMPORTANT: an IP lookup is accurate to a town at best, and can be"
        echo "tens of kilometres out. The service shows whichever aircraft is"
        echo "closest to this position, so a wrong one shows the wrong aircraft."
        echo "Correct it below if you know your real coordinates."
    else
        echo "Note: the lookup returned no usable position. Enter it by hand below."
    fi
    echo ""
}

# ---------------------------------------------------------
# read_network_credentials
#
# Prompts for how the Pi gets online. A blank SSID selects
# Ethernet instead of Wi-Fi.
#
# Sets NET_MODE (wifi|ethernet), WIFI_SSID, WIFI_PASS and
# WIFI_COUNTRY.
# ---------------------------------------------------------
read_network_credentials() {
    read -p "Enter Wi-Fi SSID for the Pi [leave blank to use Ethernet instead]: " WIFI_SSID

    if [ -z "${WIFI_SSID}" ]; then
        NET_MODE="ethernet"
        WIFI_PASS=""
        WIFI_COUNTRY=""
        echo "No SSID given: the Pi will be configured for wired Ethernet."
        echo ""
        return 0
    fi

    NET_MODE="wifi"
    read -s -p "Enter Wi-Fi Password [leave blank for an open network]: " WIFI_PASS
    echo ""

    # DietPi ships with GB. The country sets the regulatory domain, and a Pi
    # using the wrong one can fail to see or join a network on the upper 2.4GHz
    # channels, which looks exactly like a bad password on a headless board.
    local default_country="${GEO_COUNTRY:-}"
    read -p "Enter Wi-Fi country code (2 letters, e.g. CA, US, GB)${default_country:+ [${default_country}]}: " WIFI_COUNTRY
    WIFI_COUNTRY="$(echo "${WIFI_COUNTRY}" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')"
    [ -z "${WIFI_COUNTRY}" ] && WIFI_COUNTRY="${default_country}"

    if [ -n "${WIFI_COUNTRY}" ] && ! is_country_code "${WIFI_COUNTRY}"; then
        echo "Error: '${WIFI_COUNTRY}' is not a two-letter country code."
        exit 1
    fi
    echo ""

    echo "NOTE: DietPi gives Wi-Fi priority on first boot and disables Ethernet"
    echo "when both are configured, so a cable will not be a fallback if these"
    echo "credentials are wrong. Re-run this script to fix them."
    echo ""
}

# ---------------------------------------------------------
# read_install_mode
#
# Asks whether first boot should install Airspace Monitor,
# or just bring up a bare, reachable DietPi.
#
# Bare is the mode to flash when something in the install is
# misbehaving: the board comes up configured and on the
# network with nothing of ours having run, so the install
# steps can be run one at a time by hand and watched. Answer
# yes here to go back to a hands-off install; nothing else
# needs changing.
#
# Sets INSTALL_MODE (automated|bare).
# ---------------------------------------------------------
read_install_mode() {
    echo "============================================================"
    echo "First boot: install Airspace Monitor, or leave the Pi bare?"
    echo ""
    echo "  yes - DietPi installs everything unattended (30-60 minutes),"
    echo "        registers both services and reboots once. The normal choice."
    echo ""
    echo "  no  - DietPi configures the password, network, hostname and time"
    echo "        zone, then stops. Nothing of ours runs, no services are"
    echo "        installed. os/setup.sh is still copied onto the card so its"
    echo "        steps can be run by hand over SSH. Use this to find out"
    echo "        which step breaks the board."
    echo "============================================================"
    read -p "Run the automated install on first boot? [Y/n]: " RUN_INSTALLER

    case "${RUN_INSTALLER}" in
        [Nn]*)
            INSTALL_MODE="bare"
            echo "Bare mode: first boot will configure the Pi and stop."
            ;;
        *)
            INSTALL_MODE="automated"
            echo "Automated mode: first boot will install everything."
            ;;
    esac
    echo ""
}

# ---------------------------------------------------------
# read_appliance_settings
#
# Prompts for the rest of what a headless first boot needs:
# login password, hostname, time zone and receiver position.
#
# Sets ROOT_PASSWORD, PI_HOSTNAME, PI_TIMEZONE, HOME_LAT and
# HOME_LON.
# ---------------------------------------------------------
read_appliance_settings() {
    # DietPi ships root and dietpi both as "dietpi", and we install an SSH
    # server, so leaving it is an open door on the user's network. DietPi moves
    # this out of dietpi.txt once first run setup has applied it.
    while :; do
        read -s -p "Set a login password for the Pi (users root and dietpi): " ROOT_PASSWORD
        echo ""
        if [ -z "${ROOT_PASSWORD}" ]; then
            echo "  A password is required. DietPi's default is well known and the Pi accepts SSH."
            continue
        fi
        local confirm
        read -s -p "Confirm the password: " confirm
        echo ""
        [ "${ROOT_PASSWORD}" = "${confirm}" ] && break
        echo "  Those did not match. Try again."
    done
    echo ""

    read -p "Hostname for the Pi [airspace-monitor]: " PI_HOSTNAME
    PI_HOSTNAME="${PI_HOSTNAME:-airspace-monitor}"
    if ! is_hostname "${PI_HOSTNAME}"; then
        echo "Error: '${PI_HOSTNAME}' is not a valid hostname (letters, digits and hyphens)."
        exit 1
    fi
    echo ""

    # The service timestamps every contact and rolls the daily counters over at
    # local midnight, so UTC on a box in another zone rolls "today" over at the
    # wrong hour.
    local default_tz="${GEO_TZ:-UTC}"
    read -p "Time zone (e.g. America/Toronto) [${default_tz}]: " PI_TIMEZONE
    PI_TIMEZONE="${PI_TIMEZONE:-${default_tz}}"
    if ! is_timezone "${PI_TIMEZONE}"; then
        echo "Error: '${PI_TIMEZONE}' is not a valid time zone name."
        exit 1
    fi
    echo ""

    # Without these the appliance comes up tracking nothing: the defaults are
    # 0.0/0.0, which is in the Atlantic.
    while :; do
        read -p "Receiver latitude${GEO_LAT:+ [${GEO_LAT}]}: " HOME_LAT
        HOME_LAT="${HOME_LAT:-${GEO_LAT:-}}"
        is_latitude "${HOME_LAT}" && break
        echo "  Enter a latitude between -90 and 90, e.g. 45.4215."
    done
    while :; do
        read -p "Receiver longitude${GEO_LON:+ [${GEO_LON}]}: " HOME_LON
        HOME_LON="${HOME_LON:-${GEO_LON:-}}"
        is_longitude "${HOME_LON}" && break
        echo "  Enter a longitude between -180 and 180, e.g. -75.6972."
    done
    echo ""
}

# ---------------------------------------------------------
# set_literal_line <file> <prefix> <line>
#
# Replaces the first line starting with <prefix> with
# <line>, or appends <line> if there is no such line.
#
# Both arguments are treated as literal text, never as
# patterns. That matters: a Wi-Fi password is free to
# contain &, |, / and backslashes, every one of which means
# something else to sed and would corrupt the value or the
# whole file. The prefix is compared with awk's index() and
# the replacement arrives through the environment, so awk
# expands nothing on the way in either.
# ---------------------------------------------------------
set_literal_line() {
    local file="$1" prefix="$2" line="$3" tmp

    if ! tmp="$(mktemp)"; then
        echo "Error: Could not create a temporary file."
        exit 1
    fi

    if ! AM_PREFIX="${prefix}" AM_LINE="${line}" awk '
        BEGIN { prefix = ENVIRON["AM_PREFIX"]; line = ENVIRON["AM_LINE"] }
        !done && index($0, prefix) == 1 { print line; done = 1; next }
        { print }
        END { if (!done) print line }
    ' "${file}" > "${tmp}"; then
        rm -f "${tmp}"
        echo "Error: Could not rewrite ${file}."
        exit 1
    fi

    # Copy the contents rather than moving the file, so the directory entry on
    # the FAT boot partition is left exactly as DietPi's bootloader expects.
    if ! ${SUDO} cp "${tmp}" "${file}"; then
        rm -f "${tmp}"
        echo "Error: Could not write ${file}. Is the card write-protected?"
        exit 1
    fi
    rm -f "${tmp}"
}

# ---------------------------------------------------------
# quote_for_dietpi <value>
#
# Escapes a value for embedding inside the single quotes of
# dietpi-wifi.txt.
#
# That file is a bash script DietPi sources, so a lone
# single quote in an SSID or password ends the string early
# and the whole file dies with "unexpected EOF while looking
# for matching '" -- taking the Wi-Fi config with it.
# dietpi-wifi.txt says as much itself: replace ' with '\''.
# ---------------------------------------------------------
quote_for_dietpi() {
    local value="$1"
    local quote="'"
    local escaped="'\\''"
    printf '%s' "${value//${quote}/${escaped}}"
}

# ---------------------------------------------------------
# inject_boot_config <mount_dir>
#
# Writes our automation settings, Wi-Fi credentials and
# first-boot script into a mounted DietPi boot partition.
#
# Expects WIFI_SSID, WIFI_PASS and WIFI_COUNTRY to be set,
# and ROOT_DIR to point at the repo.
# ---------------------------------------------------------
inject_boot_config() {
    local mount_dir="$1"

    if [ ! -f "${mount_dir}/dietpi.txt" ]; then
        echo "Error: ${mount_dir} does not look like a DietPi boot partition (no dietpi.txt)."
        exit 1
    fi

    # Everything this needs is checked before the first write. Discovering a
    # missing value halfway through leaves a card that is neither the old
    # configuration nor the new one, which is the worst of both.
    local required missing=0
    for required in INSTALL_MODE NET_MODE ROOT_PASSWORD PI_HOSTNAME PI_TIMEZONE HOME_LAT HOME_LON; do
        if [ -z "${!required:-}" ]; then
            echo "Error: ${required} is not set; the prompts did not complete."
            missing=1
        fi
    done
    if [ "${NET_MODE:-}" = "wifi" ] && [ -z "${WIFI_SSID:-}" ]; then
        echo "Error: NET_MODE is wifi but no SSID was given."
        missing=1
    fi
    [ "${missing}" -eq 0 ] || exit 1

    echo "Configuring dietpi.txt..."
    set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_AUTOMATED=" "AUTO_SETUP_AUTOMATED=1"

    # In bare mode DietPi still does its own unattended first run -- password,
    # network, hostname, time zone, SSH -- but is told to run no custom script,
    # so nothing of ours executes on the board at all.
    if [ "${INSTALL_MODE}" = "bare" ]; then
        set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_CUSTOM_SCRIPT_EXEC=" "AUTO_SETUP_CUSTOM_SCRIPT_EXEC=0"
    else
        set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_CUSTOM_SCRIPT_EXEC=" "AUTO_SETUP_CUSTOM_SCRIPT_EXEC=1"
    fi

    # -2 is OpenSSH. Dropbear (-1, the image default) ships no sftp server, so
    # sftp and any recent scp -- which speaks the sftp protocol now -- cannot
    # copy the contact history off the Pi.
    set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_SSH_SERVER_INDEX=" "AUTO_SETUP_SSH_SERVER_INDEX=-2"

    # Left at -1 the survey is asked about on first call, which has no answer
    # on a board nobody is sitting at. Opt out and move on.
    set_literal_line "${mount_dir}/dietpi.txt" "SURVEY_OPTED_IN=" "SURVEY_OPTED_IN=0"

    # Replaces the well-known default of "dietpi" on a board that now accepts
    # SSH. DietPi encrypts this out of dietpi.txt during first run setup.
    set_literal_line "${mount_dir}/dietpi.txt" \
        "AUTO_SETUP_GLOBAL_PASSWORD=" "AUTO_SETUP_GLOBAL_PASSWORD=${ROOT_PASSWORD}"

    # So the dashboard answers on a name instead of whatever address the router
    # handed out. setup.sh installs the mDNS responder that publishes it.
    set_literal_line "${mount_dir}/dietpi.txt" \
        "AUTO_SETUP_NET_HOSTNAME=" "AUTO_SETUP_NET_HOSTNAME=${PI_HOSTNAME}"

    # Contact history is timestamped and the daily counters roll over at local
    # midnight, so the box needs to know which midnight that is.
    set_literal_line "${mount_dir}/dietpi.txt" \
        "AUTO_SETUP_TIMEZONE=" "AUTO_SETUP_TIMEZONE=${PI_TIMEZONE}"

    # 4 is "daemon + drift": kept in sync continuously rather than at boot and
    # once a day, so a drifting clock does not misdate the visit history.
    set_literal_line "${mount_dir}/dietpi.txt" "CONFIG_NTP_MODE=" "CONFIG_NTP_MODE=4"

    # Off. It would otherwise offer a dialogue on first login that nobody is
    # there to answer, and the case this project ships covers the GPIO header,
    # so a serial console is not a recovery path that can actually be reached.
    # The install log written to this partition is the diagnostic instead.
    set_literal_line "${mount_dir}/dietpi.txt" "CONFIG_SERIAL_CONSOLE_ENABLE=" "CONFIG_SERIAL_CONSOLE_ENABLE=0"

    # Left on DHCP deliberately. Converting the lease to a static address does
    # pin the dashboard's address, but it also stops the board renewing its
    # lease, so it drops out of the router's device list and looks missing
    # while it is merely quiet -- during a long first boot that is exactly when
    # you want to watch it. A DHCP reservation on the router pins the address
    # without hiding the board.
    set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_DHCP_TO_STATIC=" "AUTO_SETUP_DHCP_TO_STATIC=0"

    if [ "${NET_MODE}" = "ethernet" ]; then
        echo "Configuring wired Ethernet..."
        set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_NET_ETHERNET_ENABLED=" "AUTO_SETUP_NET_ETHERNET_ENABLED=1"
        set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_NET_WIFI_ENABLED=" "AUTO_SETUP_NET_WIFI_ENABLED=0"
    else
        set_literal_line "${mount_dir}/dietpi.txt" "AUTO_SETUP_NET_WIFI_ENABLED=" "AUTO_SETUP_NET_WIFI_ENABLED=1"

        if [ -n "${WIFI_COUNTRY:-}" ]; then
            set_literal_line "${mount_dir}/dietpi.txt" \
                "AUTO_SETUP_NET_WIFI_COUNTRY_CODE=" "AUTO_SETUP_NET_WIFI_COUNTRY_CODE=${WIFI_COUNTRY}"
        fi

        echo "Configuring Wi-Fi credentials..."
        if [ ! -f "${mount_dir}/dietpi-wifi.txt" ]; then
            echo "Error: ${mount_dir}/dietpi-wifi.txt is missing. Cannot set Wi-Fi credentials."
            exit 1
        fi

        # Slot 0 of the SSID/key arrays. These are the two values a user types,
        # so they are the two that must survive whatever is in them.
        set_literal_line "${mount_dir}/dietpi-wifi.txt" \
            "aWIFI_SSID[0]=" "aWIFI_SSID[0]='$(quote_for_dietpi "${WIFI_SSID}")'"
        set_literal_line "${mount_dir}/dietpi-wifi.txt" \
            "aWIFI_KEY[0]=" "aWIFI_KEY[0]='$(quote_for_dietpi "${WIFI_PASS}")'"

        # The image ships every slot as WPA-PSK. An open network needs NONE, or
        # wpa_supplicant waits for a handshake that never comes and the board
        # never joins -- with nothing on a headless Pi to say why.
        if [ -z "${WIFI_PASS}" ]; then
            echo "No password given; configuring slot 0 as an open network."
            set_literal_line "${mount_dir}/dietpi-wifi.txt" "aWIFI_KEYMGR[0]=" "aWIFI_KEYMGR[0]='NONE'"
        else
            set_literal_line "${mount_dir}/dietpi-wifi.txt" "aWIFI_KEYMGR[0]=" "aWIFI_KEYMGR[0]='WPA-PSK'"
        fi
    fi

    # ---------------------------------------------------------
    # Our own settings, for setup.sh to pick up on first boot.
    #
    # config.json does not exist yet -- the repo is not cloned until first boot
    # -- so the receiver position is parked here and seeded from the Pi once
    # there is somewhere to put it. Plain KEY=VALUE, and setup.sh reads the
    # values out rather than sourcing the file.
    # ---------------------------------------------------------
    echo "Writing receiver location for first boot..."
    printf '%s\n' \
        "# Written by scripts/flash.sh. Read by os/setup.sh on first boot." \
        "HOME_LAT=${HOME_LAT}" \
        "HOME_LON=${HOME_LON}" \
        | ${SUDO} tee "${mount_dir}/airspace-monitor.conf" > /dev/null

    if [ ! -f "${ROOT_DIR}/os/setup.sh" ]; then
        echo "Error: Could not find ${ROOT_DIR}/os/setup.sh to copy."
        exit 1
    fi

    # Always placed on the card under its own name, in either mode. In bare
    # mode DietPi ignores it and it is simply there to be read and run by
    # hand; it is also readable from any laptop that can mount the card.
    #
    # LF endings, because it is run by bash on the Pi and a checkout on
    # Windows may well hold it as CRLF, which the Pi answers with
    # "bad interpreter: /bin/bash^M" and no installed service.
    echo "Copying setup.sh onto the card..."
    if ! tr -d '\r' < "${ROOT_DIR}/os/setup.sh" \
        | ${SUDO} tee "${mount_dir}/airspace-monitor-setup.sh" > /dev/null; then
        echo "Error: Could not write setup.sh to ${mount_dir}."
        exit 1
    fi

    # Only this filename makes DietPi run it on first boot, so its presence or
    # absence is what separates the two modes on the card.
    if [ "${INSTALL_MODE}" = "bare" ]; then
        ${SUDO} rm -f "${mount_dir}/Automation_Custom_Script.sh"
        echo "Bare mode: no first-boot script registered. Nothing of ours will run."
    else
        echo "Registering the first-boot script..."
        if ! ${SUDO} cp "${mount_dir}/airspace-monitor-setup.sh" \
                "${mount_dir}/Automation_Custom_Script.sh"; then
            echo "Error: Could not write the first-boot script to ${mount_dir}."
            exit 1
        fi
        # FAT carries no permission bits, so this is expected to be a no-op
        # there. DietPi runs the script through bash either way.
        ${SUDO} chmod +x "${mount_dir}/Automation_Custom_Script.sh" 2>/dev/null || true
    fi

    # Verify rather than trust: a full or read-only card fails quietly here,
    # and the next thing that would notice is a Pi that never comes up.
    local want_exec="1"
    [ "${INSTALL_MODE}" = "bare" ] && want_exec="0"
    if ! ${SUDO} grep -q "^AUTO_SETUP_CUSTOM_SCRIPT_EXEC=${want_exec}\$" "${mount_dir}/dietpi.txt" \
            || [ ! -f "${mount_dir}/airspace-monitor-setup.sh" ]; then
        echo "Error: The boot partition did not take our changes. Is the card write-protected or full?"
        exit 1
    fi

    # Bare means bare: check the one file that would undo it is really gone.
    if [ "${INSTALL_MODE}" = "bare" ] && [ -f "${mount_dir}/Automation_Custom_Script.sh" ]; then
        echo "Error: Automation_Custom_Script.sh is still on the card; first boot would run it."
        exit 1
    fi
}
