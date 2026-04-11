import copy
import numpy as np
from datetime import datetime
from typing import Optional

from pint.facets.plain import PlainQuantity

from .battery import BatteryModel
from .energy_model import EnergyModel
from .weather_model import WeatherAPI
from units import Q_


class VehicleModel:
    def __init__(self, init_params: dict[str, PlainQuantity[float]]):
        self.battery_model: BatteryModel = BatteryModel()
        self.models: list[EnergyModel] = []
        self.init_params = init_params
        self.params: dict[str, PlainQuantity[float]] = copy.deepcopy(init_params)
        self.weather_model: Optional[WeatherAPI] = None

    def reset(self):
        self.params = copy.deepcopy(self.init_params)

    def add_model(self, model: EnergyModel):
        self.models.append(model)

    def set_battery_model(self, model: BatteryModel):
        self.battery_model = model

    def set_weather_model(self, model: WeatherAPI):
        self.weather_model = model

    def _update_weather(self):
        if self.weather_model is not None and "current_time_ts" in self.params:
            current_time = datetime.fromtimestamp(
                self.params["current_time_ts"].magnitude
            )
            weather = self.weather_model.get_weather_at_time(current_time)
            self.params["weather_temperature"] = Q_(weather["temperature"], "celsius")
            self.params["weather_cloud_cover"] = Q_(
                weather["cloud_cover"], "dimensionless"
            )
            self.params["weather_wind_speed"] = Q_(weather["wind_speed"], "m/s")
            self.params["weather_wind_direction"] = Q_(
                weather["wind_direction"], "degree"
            )
            self.params["weather_precipitation"] = Q_(weather["precipitation"], "mm")

    def update_dynamic(self, velocities_si: np.ndarray, sub_dt: float):
        """Run all models with the sub-timestep velocity vector, then battery and clamp."""
        self._update_weather()

        for m in self.models:
            self.params["total_energy"] += m.update_dynamic(
                self.params, velocities_si, sub_dt
            )

        self.params["total_energy"] += self.battery_model.update_dynamic(
            self.params, velocities_si, sub_dt
        )

        self.params["total_energy"] = max(
            min(self.params["total_energy"], self.params["battery_max_energy"]),
            Q_(0, "Wh"),
        )

    def print_params(self):
        for k, p in self.params.items():
            print(k, p)
