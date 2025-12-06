from models.base import EnergyModel

from typing import override
from pint import Quantity 

class SCPRollingResistanceModel(EnergyModel):
    def __init__(self): 
        super().__init__()

    @override
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        # TODO
        params['total_mu'] = params['mu_rr'] + params['mu2_rr'] * params['velocity']
        params['normal_force'] = (params['weight'] * params['grav_accel']).to('N')
        params['rolling_resistance_force'] = (params['normal_force'] * params['total_mu'])
        params['rolling_resistance_power'] = -(params['rolling_resistance_force'] * params['velocity']).to('watts')
        return (params['rolling_resistance_power'] * timestep).to('Wh')
