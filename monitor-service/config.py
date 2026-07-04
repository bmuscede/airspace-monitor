import json
import os
import subprocess

class ConfigManager:
    def __init__(self, configPath="config.json"):
        self.configPath = configPath
        self.wpaSupplicantPath = "/etc/wpa_supplicant/wpa_supplicant.conf"
        
        # Default configuration template.
        # Add new configuration parameters here.
        self.defaultConfig = {
            "flightaware_url": "https://aeroapi.flightaware.com/aeroapi",
            "flightaware_api_key": "",
            "cache_ttl": 3600,
            "home_lat": 0,
            "home_lon": 0,
            "max_radar_range_nm": 50
        }
        
        # Ensure config file exists on startup
        if not os.path.exists(self.configPath):
            self.SaveConfig(self.defaultConfig)

    def LoadConfig(self):
        """Reads the application configuration from disk."""
        try:
            with open(self.configPath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ConfigManager] Error loading config: {e}")
            return self.defaultConfig

    def SaveConfig(self, newData):
        """Merges and saves application configuration to disk."""
        currentConfig = self.LoadConfig()
        currentConfig.update(newData)
        
        try:
            with open(self.configPath, 'w') as f:
                json.dump(currentConfig, f, indent=4)
            print("[ConfigManager] Configuration saved successfully.")
            return True
        except Exception as e:
            print(f"[ConfigManager] Error saving config: {e}")
            return False

    def AddWifiNetwork(self, ssid: str, password: str):
        """
        Injects a new Wi-Fi network directly into the OS network controller.
        Requires the Python script to be running as root (which our systemd service does).
        """
        print(f"[ConfigManager] Attempting to add new Wi-Fi network: {ssid}")
        
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
                
            # Tell the OS to re-read the network file without fully rebooting
            # wpa_cli reconfigure forces the Wi-Fi chip to scan and connect to the new network
            result = subprocess.run(["wpa_cli", "-i", "wlan0", "reconfigure"], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("[ConfigManager] Wi-Fi configuration reloaded successfully.")
                return True
            else:
                print(f"[ConfigManager] Failed to reload Wi-Fi: {result.stderr}")
                return False
                
        except PermissionError:
            print("[ConfigManager] CRITICAL: Python must be run as root to modify Wi-Fi settings.")
            return False
        except Exception as e:
            print(f"[ConfigManager] Error modifying wpa_supplicant: {e}")
            return False