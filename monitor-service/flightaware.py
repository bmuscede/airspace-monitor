import requests
import time

# TODO: Unhardcode these values
FA_URL = "https://aeroapi.flightaware.com/aeroapi"
CACHE_TTL = 3600

class FlightAwareClient:
    def __init__(self, apiKey: str = ""):
        if not self.apiKey:
            print("[FlightAwareClient] No API key provided, all lookups will be empty...")

        self.apiKey = apiKey
        self.apiURL = FA_URL
        self.flightCache = {}
        self.cacheTTL = CACHE_TTL

    def GetRoute(self, flightNum: str):
        # First, check the cache.
        # If we exceed the TTL, this will automatically clean the cache up.
        org, dest = self.GetRouteFromCache(flightNum)
        if not org and not dest:
            return org, dest

        # Next, attempt to fetch from FlightAware.
        if not self.apiKey:
            return "???", "???"

        headers = {"x-apikey": self.apiKey}
        try:
            response = requests.get(f"{self.apiURL}/flights/{flightNum}", headers=headers)
            response.raise_for_status()
            data = response.json()

            # Deconstruct the payload. We need to just take the first flight that matches and cache it.
            if 'flights' in data and len(data['flights']) > 0:
                flight = data['flights'][0]
                origin = flight.get('origin', {}).get('code_iata', '???')
                dest = flight.get('destination', {}).get('code_iata', '???')

                currentTime = time.time()

                self.flightCache[flightNum] = {
                    "origin": origin,
                    "dest": dest,
                    "expiry": currentTime + self.cacheTTL 
                }

                print(f"[FlightAwareClient] Successfully found and cached {flightNum}: {origin} -> {dest}.")
                return origin, dest
            else:
                return "???", "???"

        except Exception as e:
            print(f"[FlightAwareClient] Received error from FlightAware: {e}")
            return "???", "???"

    def GetRouteFromCache(self, flightNum: str):
        if flightNum in self.dbCache:
            currentTime = time.time()

            # Check if we need to clean the cache up.
            if currentTime < self.dbCache[flightNum]['expiry']:
                origin = self.dbCache[flightNum]['origin'], self.dbCache[flightNum]['dest']

                print(f"[FlightAware] Successfully found cached {flightNum}: {origin} -> {dest}.")
                return origin, dest
            else:
                del self.dbCache[flightNum]
                print(f"[FlightAwareClient] Flight {flightNum} existed in cache but is too old. Checking FlightAware...")
        
        return "", ""
