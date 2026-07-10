import json
import os
import re
import subprocess

from utils.logs import GetLogger

CONFIG_FILE_NAME = "config.json"
class ConfigManager:
    def __init__(self, configPath=""):
        configPath = os.path.join(configPath, CONFIG_FILE_NAME)

        self.logger = GetLogger("ConfigManager")

        self.configPath = configPath
        self.wpaSupplicantPath = "/etc/wpa_supplicant/wpa_supplicant.conf"
        
        # Default configuration template.
        # Add new configuration parameters here.
        self.defaultConfig = {
            "flightaware_url": "https://aeroapi.flightaware.com/aeroapi",
            "flightaware_api_key": "",
            "cache_ttl": 3600,
            "home_lat": 0.0,
            "home_lon": 0.0,
            "max_radar_range_nm": 50
        }
        
        # Hold the active configuration in memory so callers
        # can use .Get() without re-reading disk every time.
        self._config = {}
        
        # Ensure config file exists on startup, then load into memory.
        if not os.path.exists(self.configPath):
            self._config = dict(self.defaultConfig)
            self._writeToDisk(self._config)
        else:
            self._config = self._readFromDisk()

    def Get(self, key: str, default=None):
        """
        Returns a single configuration value by key.
        Falls back to the provided default, then to the hardcoded
        default config, then to None.
        """
        if key in self._config:
            return self._config[key]
        if default is not None:
            return default
        return self.defaultConfig.get(key)

    def Set(self, key: str, value):
        """
        Updates a single configuration value in memory.
        Call SaveConfig() afterwards to persist to disk.
        """
        self._config[key] = value

    def GetAll(self):
        """Returns a copy of the full configuration dictionary."""
        return dict(self._config)

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

    def _readFromDisk(self):
        """Reads the JSON config file from disk."""
        try:
            with open(self.configPath, 'r') as f:
                loaded = json.load(f)
                # Merge with defaults so any new keys are always present.
                merged = dict(self.defaultConfig)
                merged.update(loaded)
                return merged
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return dict(self.defaultConfig)

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