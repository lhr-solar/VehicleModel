from models.energy_model import EnergyModel

from typing import override
from pint import Quantity 

# A rolling resistance model for an individual wheel
class SCPRollingResistanceModel(EnergyModel):
    def __init__(self): 
        super().__init__()

    @override
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        # TODO
        params['total_mu'] = params['mu_rr'] + params['mu2_rr'] * params['velocity']

        params['f_normal_force'] = (params['f_wheel_weight'] * params['grav_accel']).to('N')
        params['f_rr_force'] = (params['f_normal_force'] * params['total_mu'])
        params['f_rr_power'] = -(params['f_rr_force'] * params['velocity']).to('watts')

        params['r_normal_force'] = (params['r_wheel_weight'] * params['grav_accel']).to('N')
        params['r_rr_force'] = (params['r_normal_force'] * params['total_mu'])
        params['r_rr_power'] = -(params['r_rr_force'] * params['velocity']).to('watts')

        params['rr_power'] = 2 * params['f_rr_power'] + params['r_rr_power']

        return (params['rr_power'] * timestep).to('Wh')
