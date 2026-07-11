import time
from datetime import datetime
import requests
from collections import defaultdict

from utils.logs import GetLogger

class OpenweathermapClient:
    def __init__(self, api_key="", api_url="", weather_ttl=3600):
        self.logger = GetLogger("Openweathermap")

        self.api_key = api_key
        self.api_url = api_url
        self.weather_ttl = weather_ttl
        
        # Cache State Variables
        self._cached_lat = None
        self._cached_lon = None
        self._last_fetch_time = None
        self._cached_data = None

        if not self.api_key:
            self.logger.warning("No API key provided, all weather lookups will be empty...")
        if not self.api_url:
            self.logger.warning("No API URL provided, all weather lookups will be empty...")

    def _is_cache_invalid(self, lat, lon):
        """
        Evaluates whether the cache is invalid.
        There are four categories for this:
        1. There is no data cached.
        2. The weather TTL is expired.
        3. It is now after midnight.
        4. There is a different lat, lon than what we last cached.
        """
        current_time = datetime.now()

        # Condition 1: No cache exists yet.
        if self._cached_data is None or self._last_fetch_time is None:
            return True
        
        # Condition 2: TTL has expired.
        time_elapsed = (current_time - self._last_fetch_time).total_seconds()
        if time_elapsed > self.weather_ttl:
            return True

        # Condition 3: Midnight Rollover.
        if current_time.date() > self._last_fetch_time.date():
            return True

        # Condition 4: Location has changed.
        if self._cached_lat != lat or self._cached_lon != lon:
            return True

        # Cache is still perfectly valid
        return False

    def _fetch_and_parse_weather(self, lat, lon, units="metric"):
        # Build request parameters and send the request to Openweather map.
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": units
        }
        
        try:
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error is: {e}")
            return None
        
        # Extract basic data from forecast.
        city_name = data.get("city", {}).get("name", "Unknown Region")
        country = data.get("city", {}).get("country", "")
        location_name = f"{city_name}, {country}" if country else city_name

        # Grab the UTC offset (e.g., -14400 for EDT / Ottawa)
        tz_offset = data.get("city", {}).get("timezone", 0)

        # Next, build the 4 day forecast. This unfortunately means we have to aggregate due to API requirements.
        daily_blocks = defaultdict(list)
        for item in data.get("list", []):
            # Add the timezone offset to the UTC epoch timestamp to get local time
            local_timestamp = item["dt"] + tz_offset

            # Convert to a datetime string.
            from datetime import timezone
            local_date_str = datetime.fromtimestamp(local_timestamp, timezone.utc).strftime("%Y-%m-%d")
            
            daily_blocks[local_date_str].append(item)

        # Grab the current system time.
        # This assumes the timezone of the LAT, LON is the same as the system's 
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Build the unit string.
        if units == "metric":
            unit_str = "°C"
        else:
            unit_str = "°F"

        # Next, build the four day forecast by only iterating through the first 4 elements.
        forecast_array = []
        for day_date, blocks in list(daily_blocks.items())[:4]:
            # Calculate absolute max and min across all 3-hour blocks for this day
            daily_high = max(block["main"]["temp_max"] for block in blocks)
            daily_low = min(block["main"]["temp_min"] for block in blocks)

            # For now, grab the middle block to get our weather description.
            # TODO: This is not sufficient! We need an overview.
            midday_block = blocks[len(blocks) // 2]
            weather_desc = midday_block["weather"][0]["description"].capitalize()
            icon_code = midday_block["weather"][0]["icon"]

            # Check if this block's local date matches today's local date
            if day_date == today_str:
                day_name = "TODAY"
            else:
                date_obj = datetime.strptime(day_date, "%Y-%m-%d")
                day_name = date_obj.strftime("%A").upper()

            # Build the forecast object and continue.
            forecast_array.append({
                "day": day_name,
                "high": f"{round(daily_high)}{unit_str}",
                "low": f"{round(daily_low)}{unit_str}",
                "description": weather_desc,
                "icon": icon_code
            })
        
        return {
            "city_name": city_name,
            "location_name": location_name,
            "forecast": forecast_array
        }

    def get_forecast(self, lat, lon):
        # Check if we can fetch the forecast from Openweathermap.
        if not self.api_key or not self.api_url:
            return None

        # Next, check if we need to refetch data.
        if not self._is_cache_invalid(lat, lon):
            return self._cached_data
        
        # At this point, we have a cache miss.
        fresh_data = self._fetch_and_parse_weather(lat, lon)
        if fresh_data:
            self._cached_data = fresh_data
            self._cached_lat = lat
            self._cached_lon = lon
            self._last_fetch_time = datetime.now()

            self.logger.info(f"Successfully found and cached weather data for ({lat}, {lon}).")
        else:
            self.logger.warning("Fetching of weather data from API failed. Falling back to stale cached data...")
        
        return self._cached_data