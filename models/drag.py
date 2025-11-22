from models.base import Model

class SCPDragModel(Model):
    def __init__(self):
        pass

    def update(self, params: Dict[str, float]):
        # TODO
        params['drag_power'] = .5 * params['density'] * params['velocity']^3 * params['drag_coeff'] * params['frontal_area']