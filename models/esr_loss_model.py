from models.base import Model
from typing import override

class ESRBatteryLossModel(Model):
    def __init__(self):
        pass

    @override
    def update(self, params: dict[str, float]):
        #Pack Resistance
        params['pack_resistance'] = (params['cell_internal_impedence'] / params['cells_in_parallel']) * params['cells_in_series']

        #power_loss(self, current_draw: float) -> float:
        #P = I^2 * R
        params['battery_power_loss'] = (params['current_draw'] ** 2) * params['pack_resistance']
        params['total_power'] -= params['battery_power_loss']