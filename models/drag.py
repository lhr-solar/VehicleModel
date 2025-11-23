from models.base import Model
from typing import override

class SCPDragModel(Model):
    def __init__(self):
        super().__init__()

    @override
    def update(self, params: dict[str, float]):
        # TODO
        params['drag_power'] = 0.5 * params['air_density'] * params['velocity']**3 * params['drag_coeff'] * params['frontal_area']
        params['total_power'] -= params['drag_power']
