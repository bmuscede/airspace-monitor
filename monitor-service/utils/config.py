import copy
import json
import os
import re
import subprocess

from utils.logs import GetLogger

CONFIG_FILE_NAME = "config.json"

# Nested configuration options are addressed with dots: "flightaware.api_key"
# is the api_key inside the flightaware object, while "flightaware" is the
# whole object.
KEY_SEPARATOR = "."

# Tells "there is no such key" apart from "the value stored there is None".
_MISSING = object()


def _keyParts(key: str):
    """
    Splits a dotted key into its parts. Returns [] for anything unusable
    (a non-string, an empty key, or a stray dot such as "a..b").
    """
    if not isinstance(key, str) or not key:
        return []
    parts = key.split(KEY_SEPARATOR)
    return [] if any(not part for part in parts) else parts


def _copied(value):
    """Containers are handed out as copies so callers can't mutate the config."""
    return copy.deepcopy(value) if isinstance(value, (dict, list)) else value


def FlattenKeys(data: dict, prefix: str = "") -> dict:
    """
    Turns a nested configuration payload into {dotted key: value}, which is
    what ConfigManager.Set() takes. Only objects are walked into, so lists,
    scalars and empty objects come back as leaves.
    """
    flat = {}
    for key, value in data.items():
        path = f"{prefix}{KEY_SEPARATOR}{key}" if prefix else str(key)
        if isinstance(value, dict) and value:
            flat.update(FlattenKeys(value, path))
        else:
            flat[path] = value
    return flat


class ConfigManager:
    def __init__(self, configPath=""):
        configPath = os.path.join(configPath, CONFIG_FILE_NAME)

        self.logger = GetLogger("ConfigManager")

        self.configPath = configPath
        self.wpaSupplicantPath = "/etc/wpa_supplicant/wpa_supplicant.conf"
        
        # Default configuration template.
        # Add new configuration parameters here.
        self.defaultConfig = {
            # API for Flightaware
            "flightaware": {
                "url": "https://aeroapi.flightaware.com/aeroapi",
                "api_key": "",
                "cache_ttl": 3600
            },

            # API for Openweathermap
            "openweathermap": {
                "url": "https://api.openweathermap.org/data/2.5/forecast",
                "api_key": "",
                "cache_ttl": 3600,
            },

            # Radar location settings.
            "radar": {
                "home_lat": 0.0,
                "home_lon": 0.0,
                "max_range_nm": 50,
            },

            # Splitflap display settings.
            "splitflap": {
                "enabled": False,

                # Serial port of the Chainlink controller. Empty auto-detects
                # the ESP32 / T-Display USB bridge.
                "port": "",

                # How the channels below are grouped into rows of flaps, top to
                # bottom (e.g. [14, 14, 14] for three rows of fourteen). Empty
                # means every channel is one row, left to right.
                "rows": [],

                "channels": [
                    # Channels have the format of:
                    # {
                    #   "channel": 0,
                    #   "charset": "<CHARSET_NAME>"
                    # }    
                ],
                "charsets": {
                    "default": {
                        "flaps": " ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!?."
                    },
                    "alternate": {
                        "flaps": " ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890#?."
                    },
                    # Additional charsets can be defined below either as a string or array.
                },
                "auto_rehome": {
                    "enabled": True,
                    "max_attempts": 3,
                    "window_seconds": 600,
                    "backoff_seconds": 15
                },

                # Home-offset calibration state. The offsets themselves live in
                # the ESP32's flash; this only remembers whether we have ever
                # saved them, so the display calibrates itself once and not on
                # every boot. Clear "calibrated" to force it to run again.
                "calibration": {
                    "calibrated": False,
                    "calibrated_at": 0.0
                }
            },

            # Contact history settings.
            "history": {
                # How long a plane can go unheard before it is considered out of range.
                "contact_gap_seconds": 300,
                
                # How long we flush for still-open tracked planes.
                "flush_seconds": 300,

                # How long we store planes tracked.
                "retention_days": 90,
            },

            # The log level written to the live log. Persistent SD card log only stores WARNING
            # and above.
            "log_level": "INFO",
        }
        
        # Hold the active configuration in memory so callers
        # can use .Get() without re-reading disk every time.
        self._config = {}
        
        # Ensure config file exists on startup, then load into memory.
        if not os.path.exists(self.configPath):
            self._config = copy.deepcopy(self.defaultConfig)
            self._writeToDisk(self._config)
        else:
            self._config = self._readFromDisk()

    def Get(self, key: str, default=None):
        """
        Returns a single configuration value by key.
        Dots return nested configuration options. So "test.sub" returns the
        sub object of sub from test, while "test" returns the whole object.
        Falls back to the provided default, then to the hardcoded
        default config, then to None.

        Objects and lists come back as copies: mutating what Get() returns
        never changes the live configuration. Use Set() for that.
        """
        value = self._lookup(self._config, key)
        if value is not _MISSING:
            return _copied(value)
        if default is not None:
            return default
        value = self._lookup(self.defaultConfig, key)
        return _copied(value) if value is not _MISSING else None

    def Set(self, key: str, value):
        """
        Updates a single configuration value in memory.
        Objects separated with a dot are nested underneath, so
        Set("test.sub", 1) sets sub inside test, creating test if it is
        missing. Call SaveConfig() afterwards to persist to disk.
        """
        parts = _keyParts(key)
        if not parts:
            raise ValueError(f"invalid configuration key: {key!r}")

        container = self._config
        for i, part in enumerate(parts[:-1]):
            child = container.get(part)
            if not isinstance(child, dict):
                if child is not None:
                    # Refuse to bury a scalar: "a.b" where a is 5 is a bug in
                    # the caller, not something to silently paper over.
                    raise ValueError(
                        f"cannot set {key!r}: {KEY_SEPARATOR.join(parts[:i + 1])} is not an object"
                    )
                child = {}
                container[part] = child
            container = child

        container[parts[-1]] = copy.deepcopy(value) if isinstance(value, (dict, list)) else value

    def Has(self, key: str) -> bool:
        """True when the key exists in the active config or in the defaults."""
        return (self._lookup(self._config, key) is not _MISSING
                or self._lookup(self.defaultConfig, key) is not _MISSING)

    def GetAll(self):
        """Returns a copy of the full configuration dictionary."""
        return copy.deepcopy(self._config)

    def SaveConfig(self):
        """
        Writes the current in-memory config state to disk.
        """
        return self._writeToDisk(self._config)

    def GetWifiNetworks(self):
        """
        Parses /etc/wpa_supplicant/wpa_supplicant.conf and extracts
        all configured network SSIDs.
        
        Returns a list of dicts: [{"ssid": "MyNetwork"}, ...]
        """
        networks = []
        try:
            with open(self.wpaSupplicantPath, 'r') as f:
                content = f.read()
            
            # Match all network={...} blocks and extract the ssid line.
            pattern = r'network\s*=\s*\{[^}]*ssid\s*=\s*"([^"]+)"[^}]*\}'
            matches = re.findall(pattern, content)
            
            for ssid in matches:
                networks.append({"ssid": ssid})
                
        except FileNotFoundError:
            self.logger.warning("wpa_supplicant.conf not found. No Wi-Fi networks to list.")
        except Exception as e:
            self.logger.error(f"Error reading wpa_supplicant: {e}")
        
        return networks

    def AddWifiNetwork(self, ssid: str, password: str):
        """
        Injects a new Wi-Fi network directly into the OS network controller.
        Requires the Python script to be running as root (which our systemd service does).
        """
        self.logger.info(f"Attempting to add new Wi-Fi network: {ssid}")
        
        # Format the block required by Debian's wpa_supplicant
        networkBlock = f"""
network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""
        try:
            # Append the new network to the configuration file
            with open(self.wpaSupplicantPath, 'a') as f:
                f.write(networkBlock)
                
            # Tell the OS to re-read the network file without fully rebooting.
            # wpa_cli reconfigure forces the Wi-Fi chip to scan and connect to the new network.
            result = subprocess.run(["wpa_cli", "-i", "wlan0", "reconfigure"], capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Wi-Fi configuration reloaded successfully.")
                return True
            else:
                self.logger.error(f"Failed to reload Wi-Fi: {result.stderr}")
                return False
                
        except PermissionError:
            self.logger.error("CRITICAL: Python must be run as root to modify Wi-Fi settings.")
            return False
        except Exception as e:
            self.logger.error(f"Error modifying wpa_supplicant: {e}")
            return False

    def RemoveWifiNetwork(self, ssid: str):
        """
        Removes a Wi-Fi network from wpa_supplicant.conf by SSID.
        
        Parses the file, finds the network={} block containing the
        target SSID, removes it, writes the file back, and triggers
        wpa_cli reconfigure.
        """
        self.logger.info(f"Attempting to remove Wi-Fi network: {ssid}")

        try:
            with open(self.wpaSupplicantPath, 'r') as f:
                content = f.read()

            # Match the specific network block for this SSID.
            # This regex captures the full network={...} block including any
            # leading whitespace/newlines before it.
            pattern = r'\n?network\s*=\s*\{[^}]*ssid\s*=\s*"' + re.escape(ssid) + r'"[^}]*\}\n?'
            newContent, count = re.subn(pattern, '\n', content)

            if count == 0:
                self.logger.warning(f"Wi-Fi network '{ssid}' not found in wpa_supplicant.conf.")
                return False

            with open(self.wpaSupplicantPath, 'w') as f:
                f.write(newContent)

            # Reconfigure the wireless interface.
            result = subprocess.run(["wpa_cli", "-i", "wlan0", "reconfigure"], capture_output=True, text=True)

            if result.returncode == 0:
                self.logger.info(f"Wi-Fi network '{ssid}' removed and config reloaded.")
                return True
            else:
                self.logger.error(f"Failed to reload Wi-Fi after removal: {result.stderr}")
                return False

        except PermissionError:
            self.logger.error("CRITICAL: Python must be run as root to modify Wi-Fi settings.")
            return False
        except Exception as e:
            self.logger.error(f"Error removing Wi-Fi network: {e}")
            return False

    # --- Private Helpers ---

    @staticmethod
    def _lookup(container: dict, key: str):
        """
        Walks a dotted key through nested dicts.
        Returns _MISSING when any part of the path isn't there.
        """
        parts = _keyParts(key)
        if not parts:
            return _MISSING

        current = container
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return _MISSING
            current = current[part]
        return current

    @classmethod
    def _mergeWithDefaults(cls, defaults: dict, loaded: dict) -> dict:
        """
        Overlays the config file on the defaults, object by object.

        A shallow update would drop every new key inside a nested object the
        file happens to carry an older copy of (a config written before
        "splitflap.calibration" existed would hide it entirely), so nested
        objects are merged rather than replaced. Lists and scalars are taken
        from the file as-is.
        """
        merged = copy.deepcopy(defaults)
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = cls._mergeWithDefaults(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    def _readFromDisk(self):
        """Reads the JSON config file from disk."""
        try:
            with open(self.configPath, 'r') as f:
                loaded = json.load(f)

            # Merge with defaults so any new keys are always present.
            return self._mergeWithDefaults(self.defaultConfig, loaded)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return copy.deepcopy(self.defaultConfig)

    def _writeToDisk(self, data: dict):
        """Writes the configuration dictionary to disk as JSON."""
        try:
            with open(self.configPath, 'w') as f:
                json.dump(data, f, indent=4)
            self.logger.info("Configuration saved successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            return False