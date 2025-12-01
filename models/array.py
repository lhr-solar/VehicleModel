from models.base import EnergyModel
from typing import override
from pint import Quantity 
import math

class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        params["array_power"] = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]
        return params["array_power"] * timestep


class SCPArrayModelWithIncidence(EnergyModel):
    def __init__(self):
        super().__init__()

    def _incidence_factor(self, params: dict[str, Quantity[float]]) -> float:
        # Compute how much sunlight hits the array (0–1)
        # based on time of day + latitude.
       
    
        # Extract raw numbers
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        # Convert latitude to radians
        lat = math.radians(lat_deg)

        # Time of day in hours
        time_hours = timestamp / 3600.0

        # Hour angle: 0 at noon
        h = (time_hours - 12.0) * math.pi / 12.0

        # Simple declination (equinox)
        dec = 0.0

        # Solar elevation angle formula from book
        sin_alpha = (
            math.sin(lat) * math.sin(dec) +
            math.cos(lat) * math.cos(dec) * math.cos(h)
        )
        sin_alpha = max(-1.0, min(1.0, sin_alpha))

        if sin_alpha <= 0:
            return 0.0  # sun below horizon → no power

        return sin_alpha

    @override
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        # Updates array power based on sun angle
        # accumulates energy into total_array_energy.

        # sunlight factor 0–1
        factor = self._incidence_factor(params)

        # base max power
        base_power = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]

        # actual array power this timestep
        params["array_power"] = base_power * factor

        # accumulate energy (Power × time)
        params["total_array_energy"] += params["array_power"] * timestep

        # advance timestamp
        params["timestamp"] = params["timestamp"] + timestep.magnitude

        # return energy produced this timestep
        return params["array_power"] * timestep

