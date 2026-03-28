import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict


class WeatherAPI:
    def __init__(self):
        self.weather_data = None

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
            "hourly": "temperature_2m,cloud_cover,wind_speed_10m,wind_direction_10m,precipitation",
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
                    "cloud_cover": hourly["cloud_cover"],  # %
                    "wind_speed": hourly["wind_speed_10m"],  # m/s
                    "wind_direction": hourly["wind_direction_10m"],  # degrees (0-360)
                    "precipitation": hourly["precipitation"],  # mm (preceding hour sum)
                }
            )

            self.weather_data = weather_df
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

