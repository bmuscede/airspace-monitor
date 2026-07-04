import os
import csv
import requests
import logs

# TODO: Unhardcode this value!
DB_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"

class AircraftDatabase:
    def __init__(self, dbPath: str):
        self.logger = logs.GetLogger("AircraftDatabase")

        self.dbPath = dbPath
        self.dbURL = DB_URL

        self.dbCache = {}
        self.isUpdating = False
        if os.path.exists(self.dbPath):
            self.LoadIntoMemory()

    def DownloadDatabase(self):
        if self.isUpdating:
            # Already updating so just abort.
            return False

        self.isUpdating = True
        self.logger.info("Starting database download...")

        try:
            with requests.get(self.dbURL, stream=True) as req:
                req.raise_for_status()
                with open(self.dbPath, 'wb') as dbFile:
                    for chunk in req.iter_content(chunk_size=8192):
                        dbFile.write(chunk)
            
            self.logger.info("Download of aircraft database completed.")
            self.LoadIntoMemory()
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to download: {e}")
            return False

        finally:
            self.isUpdating = False

    def LoadIntoMemory(self):
        self.logger.info("Loading aircraft database into RAM...")

        try:
            with open(self.dbPath, mode='r', encoding='utf-8') as dbFile:
                tempCache = {}

                reader = csv.DictReader(dbFile)
                for row in reader:
                    hexCode = row.get('icao24', '').strip().lower()
                    if hexCode:
                        tempCache[hexCode] = {
                            "type": row.get('typecode', '???').strip(),
                            "reg": row.get('registration', '???').strip()
                        }
                
                self.dbCache = tempCache
        
            self.logger.info(f"Successfully loaded {len(self.dbCache)} aircraft records into memory.")
        
        except Exception as e:
            self.logger.error(f"Failed to load aircraft CSV: {e}")

    def GetAircraftInfo(self, hexCode: str):
        # Ensure the hexcode is all lowercase first.
        cleanHexCode = hexCode.strip().lower()
        return self.dbCache.get(cleanHexCode, {"type": "???", "reg": "???"})
