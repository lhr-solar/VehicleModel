from models.base import EnergyModel

from typing import override
from pint import Quantity 

# A rolling resistance model for an individual wheel
class SCPRollingResistanceModel(EnergyModel):
    def __init__(self, wheel_weight): 
        super().__init__()
        self.wheel_weight = wheel_weight

    @override
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        # TODO
        params['total_mu'] = params['mu_rr'] + params['mu2_rr'] * params['velocity']
        params['normal_force'] = (self.wheel_weight * params['grav_accel']).to('N')
        params['rolling_resistance_force'] = (params['normal_force'] * params['total_mu'])
        params['rolling_resistance_power'] = -(params['rolling_resistance_force'] * params['velocity']).to('watts')
        return (params['rolling_resistance_power'] * timestep).to('Wh')
