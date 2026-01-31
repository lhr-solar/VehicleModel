from models.energy_model import EnergyModel
try:
    from typing import override  # Python 3.12+
except ImportError:
    from typing_extensions import override  # type: ignore
from pint.facets.plain import PlainQuantity
from pint import Quantity


class SCPDragModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        params["drag_power"] = -(
            0.5
            * params["air_density"]
            * params["velocity"] ** 3
            * params["drag_coeff"]
            * params["frontal_area"]
        ).to("watts")
        return params["drag_power"] * timestep
