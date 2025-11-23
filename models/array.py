from models.base import EnergyModel
from typing import override
from pint import Quantity 

class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        params["array_power"] = params["num_cells"] * params["p_mpp"]
        return params["array_power"] * timestep
