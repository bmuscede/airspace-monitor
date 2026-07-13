import math
import cairosvg
from typing import Optional

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points
    on Earth using the Haversine formula.

    Returns distance in nautical miles.
    """
    # Earth's radius in nautical miles
    R = 3440.065

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(dlon / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the initial bearing (forward azimuth) from point 1 to point 2.

    Returns bearing in degrees (0-360, clockwise from north).
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_rad)
    y = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))

    initial_bearing = math.atan2(x, y)
    compass_bearing = (math.degrees(initial_bearing) + 360) % 360

    return round(compass_bearing, 1)

def get_svg_filename_from_code(weather_code: str) -> str:
     owm_code_to_svg_map = {
          # Clear Sky
          "01d": "clear-day.svg",
          "01n": "clear-night.svg",

          # Few Clouds
          "02d": "partly-cloudy-day.svg",
          "02n": "partly-cloudy-night.svg",

          # Scattered Clouds
          "03d": "cloudy.svg",  
          "03n": "cloudy.svg",

          # Broken/Overcast Clouds
          "04d": "overcast-day.svg", 
          "04n": "overcast-night.svg",

          # Shower Rain
          "09d": "drizzle.svg",  
          "09n": "drizzle.svg",

          # Rain
          "10d": "rain.svg",     
          "10n": "rain.svg",

          # Thunderstorm
          "11d": "thunderstorm.svg",
          "11n": "thunderstorm.svg",
          
          # Snow
          "13d": "snow.svg",
          "13n": "snow.svg",
          
          # Mist / Fog
          "50d": "mist.svg",
          "50n": "mist.svg",
     }

     if weather_code in owm_code_to_svg_map:
          return owm_code_to_svg_map[weather_code]
     
     return "not-available.svg"

def svg_to_png(svg_path: str, png_path: str, output_width: Optional[int] = None, output_height: Optional[int] = None, dpi: int = 96) -> bool:
    # Use the cairosvg library to convert to PNG
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=output_width, output_height=output_height, dpi=dpi)
    return True
