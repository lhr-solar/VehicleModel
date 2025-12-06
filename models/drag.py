from models.energy_model import EnergyModel
from typing import override
from pint import Quantity 

class SCPDragModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        params['drag_power'] = -(0.5 * params['air_density'] * params['velocity']**3 * params['drag_coeff'] * params['frontal_area']).to('watts')
        return params['drag_power'] * timestep
