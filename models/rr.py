from models.base import EnergyModel
from typing import override, cast
from pint.facets.plain import PlainQuantity
from pint import Quantity

class SCPRollingResistanceModel(EnergyModel):
    def __init__(self): 
        super().__init__()

    @override
    def update(self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]) -> PlainQuantity[float]:
        # TODO
        params['total_mu'] = cast(PlainQuantity[float], params['mu_rr'] + params['mu2_rr'] * params['velocity'])
        params['normal_force'] = (params['weight'] * params['grav_accel']).to('N')
        params['rolling_resistance_force'] = (params['normal_force'] * params['total_mu'])
        params['rolling_resistance_power'] = -(params['rolling_resistance_force'] * params['velocity']).to('watts')
        return (params['rolling_resistance_power'] * timestep).to('Wh')
