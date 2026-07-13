import requests
import time
import math
from typing import Tuple, List, Dict, Any

from utils.logs import GetLogger

class FlightAwareClient:
    def __init__(self, apiKey: str = "", apiURL: str = "", cacheTTL: int = 3600):
        self.logger = GetLogger("FlightAware")

        self.apiKey = apiKey
        self.apiURL = apiURL
        self.cacheTTL = cacheTTL
        self.flightCache = {}

        if not self.apiKey:
            self.logger.warning("No API key provided, all lookups will be empty...")

    def GetRoute(self, flightNum: str) -> Tuple[str, str]:
        """
        Attempts to resolve origin and destination for a given flight number.
        First checks the TTL cache, then falls back to the FlightAware API.
        """
        # First, check the cache.
        # If we get a hit, return immediately.
        org, dest = self.GetRouteFromCache(flightNum)
        if org and dest:
            return org, dest

        # Next, attempt to fetch from FlightAware.
        if not self.apiKey:
            return "???", "???"

        if not self.apiURL:
            self.logger.error("No FlightAware API URL configured.")
            return "???", "???"

        headers = {"x-apikey": self.apiKey}
        try:
            response = requests.get(f"{self.apiURL}/flights/{flightNum}", headers=headers)
            response.raise_for_status()
            data = response.json()

            # Deconstruct the payload. We need to just take the first flight that matches and cache it.
            if 'flights' in data and len(data['flights']) > 0:
                flight = data['flights'][0]

                # Get the origin -> destination.
                # Aeroapi fills in fields even if they don't exist which means that we have to handle both null and non-existent entries.
                origin_data = flight.get('origin', {})
                destination_data = flight.get('destination', {})

                origin = '???' if origin_data is None else origin_data.get('code_iata', '???')
                destination = '???' if destination_data is None else destination_data.get('code_iata', '???')

                currentTime = time.time()

                self.flightCache[flightNum] = {
                    "origin": origin,
                    "dest": destination,
                    "expiry": currentTime + self.cacheTTL 
                }

                self.logger.info(f"Successfully found and cached {flightNum}: {origin} -> {destination}.")
                return origin, destination
            else:
                return "???", "???"

        except Exception as e:
            self.logger.error(f"Received error from FlightAware: {e}")
            return "???", "???"

    def GetNearbyFlights(self, lat: float, lon: float, radius_nm: float) -> List[Dict[str, Any]]:
        """
        Simulates an antenna by querying FlightAware for flights 
        within a bounding box around the home coordinates.
        """
        if not self.apiKey:
            return []

        if not self.apiURL:
            self.logger.error("No FlightAware API URL configured.")
            return "???", "???"
    
        # Convert radius from nautical miles to degrees for the bounding box.
        lat_offset = radius_nm / 60.0
        lon_offset = radius_nm / (60.0 * math.cos(math.radians(lat)))
        min_lat = lat - lat_offset
        max_lat = lat + lat_offset
        min_lon = lon - lon_offset
        max_lon = lon + lon_offset

        # Create the bounding box using the -latlong keyword.
        # We MUST wrap the four coordinates in literal double quotes so FlightAware parses them as one block.
        search_query = f'-latlong "{min_lat} {min_lon} {max_lat} {max_lon}"'
        search_query += " -filter airline"
        params = {
            "query": search_query
        }
        headers = {"x-apikey": self.apiKey}
        
        try:
            response = requests.get(f"{self.apiURL}/flights/search", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("flights", [])
        except Exception as e:
            self.logger.error(f"Radar sweep failed: {e}")
            return []

    def GetRouteFromCache(self, flightNum: str) -> Tuple[str, str]:
        """
        Checks the in-memory TTL cache for a previously looked up flight.
        Returns (origin, dest) on hit, or ("", "") on miss/expired.
        """
        if flightNum in self.flightCache:
            currentTime = time.time()

            # Check if the cache entry has expired.
            if currentTime < self.flightCache[flightNum]['expiry']:
                origin = self.flightCache[flightNum]['origin']
                dest = self.flightCache[flightNum]['dest']

                self.logger.info(f"Cache hit for {flightNum}: {origin} -> {dest}.")
                return origin, dest
            else:
                del self.flightCache[flightNum]
                self.logger.info(f"Flight {flightNum} existed in cache but is too old. Checking FlightAware...")
        
        return "", ""
