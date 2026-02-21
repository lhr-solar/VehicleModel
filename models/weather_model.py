import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict


class WeatherModel:
    def __init__(self):
        self.weather_data = None
        self.last_fetched_date = None

    def fetch_weather_data(
        self,
        latitude: float,
        longitude: float,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        url = "https://archive-api.open-meteo.com/v1/archive"

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "hourly": "temperature_2m,cloudcover,wind_speed_10m,wind_direction_10m,precipitation",
            "timezone": "auto",
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "hourly" not in data:
                raise ValueError("Invalid response from Open-Meteo API")

            hourly = data["hourly"]
            weather_df = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(hourly["time"]),
                    "temperature": hourly["temperature_2m"],  # °C
                    "cloud_cover": hourly["cloudcover"],  # %
                    "wind_speed": hourly["wind_speed_10m"],  # m/s
                    "wind_direction": hourly["wind_direction_10m"],  # degrees (0-360)
                    "precipitation": hourly["precipitation"],  # mm (preceding hour sum)
                }
            )

            self.weather_data = weather_df
            self.last_fetched_date = datetime.now()
            return weather_df

        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch weather data: {str(e)}")

    def get_weather_at_time(self, current_time: datetime) -> Dict[str, float]:
        if self.weather_data is None or self.weather_data.empty:
            return {
                "temperature": 25.0,
                "cloud_cover": 0.0,
                "wind_speed": 0.0,
                "wind_direction": 0.0,
                "precipitation": 0.0,
            }

        # Find closest time in weather data
        idx = (self.weather_data["datetime"] - current_time).abs().argmin()
        row = self.weather_data.iloc[idx]

        return {
            "temperature": float(row["temperature"]),
            "cloud_cover": float(row["cloud_cover"]),
            "wind_speed": float(row["wind_speed"]),
            "wind_direction": float(row["wind_direction"]),
            "precipitation": float(row["precipitation"]),
        }

    def get_temperature_modifier(self, temperature: float) -> float:
        """
        Calculate efficiency modifier based on temperature.
        Reference temperature: 25°C

        Args:
            temperature: Ambient temperature in °C

        Returns:
            Modifier factor (1.0 = no change, <1.0 = efficiency loss)
        """
        ref_temp = 25.0
        temp_coeff = -0.005  # -0.5% per °C deviation from reference

        return 1.0 + (temperature - ref_temp) * temp_coeff

    def get_cloud_cover_modifier(self, cloud_cover: float) -> float:
        # Simplified: linear reduction with cloud cover
        return 1.0 - (cloud_cover / 100.0) * 0.8  # Up to 80% loss at full cover

    def get_wind_modifier(
        self,
        wind_speed: float,
        wind_direction: float,
        vehicle_heading: float = 0,
        vehicle_speed: float = 0,
    ) -> float:
        """
        Calculate drag modifier based on relative wind.

        Args:
            wind_speed: Wind speed in m/s (from meteorological convention)
            wind_direction: Direction wind is coming FROM (0=N, 90=E, 180=S, 270=W)
            vehicle_heading: Direction vehicle is heading (0=N, 90=E, 180=S, 270=W)
            vehicle_speed: Vehicle speed in m/s

        Returns:
            Modifier factor for drag coefficient
        """
        import math

        if vehicle_speed <= 0:
            return 1.0

        # Calculate relative wind direction (wind relative to vehicle heading)
        # Headwind (blowing against you) = 0° relative
        # Tailwind (blowing behind you) = 180° relative
        relative_wind_dir = (wind_direction - vehicle_heading) % 360

        # Component of wind in direction of travel (headwind/tailwind)
        # Headwind increases drag, tailwind decreases it
        headwind_component = wind_speed * math.cos(math.radians(relative_wind_dir))

        # Effective speed through air = vehicle speed + headwind component
        # Positive headwind = faster relative motion = more drag
        relative_speed = vehicle_speed + headwind_component

        # Drag scales as v², so modifier = (v_effective / v_base)²
        # Avoid negative speeds
        if relative_speed < 0:
            relative_speed = 0

        drag_modifier = (relative_speed / vehicle_speed) ** 2

        return drag_modifier

    def get_rolling_resistance_modifier(self, precipitation: float) -> float:
        """Calculate rolling resistance modifier based on precipitation.

        Uses actual precipitation (mm/h) instead of cloud cover as a proxy.
        Light rain (~1 mm/h) gives a small increase; heavy rain (>=5 mm/h)
        saturates at ~1.2x rolling resistance (wet road).

        Args:
            precipitation: Precipitation in mm for the preceding hour.

        Returns:
            Modifier factor (1.0 = dry, up to 1.2 = heavy rain).
        """
        # Clamp precipitation contribution: 0 mm → 1.0, >=5 mm → 1.2
        clamped = min(precipitation, 5.0)
        return 1.0 + (clamped / 5.0) * 0.2
