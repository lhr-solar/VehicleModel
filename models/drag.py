from models.energy_model import EnergyModel
from typing import override
from pint.facets.plain import PlainQuantity
from pint import Quantity


class SCPDragModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        # Get wind modifier if weather is enabled
        wind_modifier = params.get("weather_wind_modifier", None)
        if wind_modifier is not None:
            drag_coeff_effective = params["drag_coeff"] * wind_modifier
        else:
            drag_coeff_effective = params["drag_coeff"]

        params["drag_power"] = -(
            0.5
            * params["air_density"]
            * params["velocity"] ** 3
            * drag_coeff_effective
            * params["frontal_area"]
        ).to("watts")
        return params["drag_power"] * timestep
