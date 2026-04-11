import math
import numpy as np
from models.energy_model import EnergyModel
from typing import override, cast
from pint.facets.plain import PlainQuantity
from units import Q_


class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        lat = math.radians(lat_deg)
        time_of_day_hours = timestamp / 3600.0
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)
        dec = 0.0

        sin_alpha = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(
            dec
        ) * math.cos(h)
        sin_alpha = max(-1.0, min(1.0, sin_alpha))

        if sin_alpha <= 0:
            return 0.0
        return sin_alpha

    @override
    def update_dynamic(
        self,
        params: dict[str, PlainQuantity[float]],
        velocities_si: np.ndarray,
        sub_dt: float,
    ) -> PlainQuantity[float]:
        outer_timestep = Q_(sub_dt * len(velocities_si), "seconds")

        factor = Q_(self._incidence_factor(params), "dimensionless")
        base_power = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]

        cloud_cover = params.get("weather_cloud_cover")
        if cloud_cover is not None:
            base_power = base_power * (1.0 - (cloud_cover.magnitude / 100.0) * 0.8)

        params["array_power"] = base_power * factor
        params["array_energy"] = cast(
            PlainQuantity[float], params["array_power"] * outer_timestep
        )
        params["total_array_energy"] += params["array_energy"]

        return params["array_energy"]
