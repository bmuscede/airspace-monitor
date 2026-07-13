from abc import ABC, abstractmethod
from typing import Optional
from models import Aircraft, StateInformation, WeatherForecast

class DisplayDriver(ABC):
    @abstractmethod
    def WriteNoFlight(self, state_info: StateInformation, forecast_data: Optional[WeatherForecast] = None):
        """Displays a no-flight or idle status on the screen."""
        pass
        
    @abstractmethod
    def WriteFlightData(self, aircraft: Aircraft):
        """Displays live flight data on the screen."""
        pass
