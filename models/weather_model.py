import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict
from pint.facets.plain import PlainQuantity
from units import Q_


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
            "hourly": "temperature_2m,cloudcover,wind_speed_10m,shortwave_radiation",
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
                    "solar_radiation": hourly["shortwave_radiation"],  # W/m²
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
                "solar_radiation": 500.0,
            }

        # Find closest time in weather data
        idx = (self.weather_data["datetime"] - current_time).abs().argmin()
        row = self.weather_data.iloc[idx]

        return {
            "temperature": float(row["temperature"]),
            "cloud_cover": float(row["cloud_cover"]),
            "wind_speed": float(row["wind_speed"]),
            "solar_radiation": float(row["solar_radiation"]),
        }

    def get_cloud_cover_modifier(self, cloud_cover: float) -> float:
        # Simplified: linear reduction with cloud cover
        return 1.0 - (cloud_cover / 100.0) * 0.8  # Up to 80% loss at full cover

    def get_wind_modifier(self, wind_speed: float, vehicle_heading: float = 0) -> float:
        # Simplified: assume headwind
        # Relative wind increases effective drag
        # Effective velocity = velocity + headwind
        # Drag scales with velocity²

        # For now, simplified assumption: headwind adds to car's speed relative to air
        # If wind_speed = 5 m/s, it's like car is moving faster through air
        # Typical car speed: ~8 m/s (20 mph)
        base_speed = 8.0
        relative_speed = base_speed + wind_speed

        # Drag scales as v², so modifier = (v_effective / v_base)²
        drag_modifier = (relative_speed / base_speed) ** 2

        return drag_modifier

    def get_rolling_resistance_modifier(self, cloud_cover: float) -> float:
        # High cloud cover = higher chance of wet roads
        # Wet roads: ~1.2x rolling resistance
        # Dry roads: 1.0x

        return 1.0 + (cloud_cover / 100.0) * 0.2
