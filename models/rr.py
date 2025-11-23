from models.base import Model
from typing import override
from pint import Quantity 

class SCPRollingResistanceModel(Model):
    def __init__(self): 
        super().__init__()

    @override
    def update(self, params: dict[str, Quantity[float]]):
        # TODO
        params['total_mu'] = params['mu'] + params['mu2'] * params['velocity']
        params['rolling_resistance'] = params['normal_force'] * params['total_mu']
        params['total_power'] -= params['rolling_resistance'] * params['velocity']
