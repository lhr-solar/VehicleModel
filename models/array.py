from models.energy_model import EnergyModel
from typing import override, cast
from pint.facets.plain import PlainQuantity
from pint import Quantity
from units import Q_
import math


class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        # Compute how much sunlight hits the array (0–1)
        # based on time of day + latitude.

        # Extract raw numbers
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        # Convert latitude to radians
        lat = math.radians(lat_deg)

        # Time of day in seconds
        time_of_day_s = timestamp

        # Convert to fractional hours for hour angle
        time_of_day_hours = time_of_day_s / 3600.0

        # Hour angle: 0 at noon, now with second-level precision
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)

        # Simple declination (equinox)
        dec = 0.0

        # Solar elevation angle formula from book
        sin_alpha = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(
            dec
        ) * math.cos(h)
        sin_alpha = max(-1.0, min(1.0, sin_alpha))

        if sin_alpha <= 0:
            return 0.0  # sun below horizon → no power

        return sin_alpha

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        # Updates array power based on sun angle
        # accumulates energy into total_array_energy.

        # sunlight factor 0–1
        factor: PlainQuantity[float] = Q_(
            self._incidence_factor(params), "dimensionless"
        )

        # base max power
        base_power = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]

        # Get cloud cover modifier if weather is enabled
        cloud_modifier = params.get("weather_cloud_modifier", None)
        if cloud_modifier is not None:
            base_power = base_power * cloud_modifier

        params["array_power"] = base_power * factor

        # energy produced this timestep (Power × time)
        params["array_energy"] = cast(
            PlainQuantity[float], params["array_power"] * timestep
        )

        # accumulate total array energy over the whole race
        params["total_array_energy"] += params["array_energy"]

        # return energy produced this timestep
        return params["array_energy"]
