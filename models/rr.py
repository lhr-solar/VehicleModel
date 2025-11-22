from models.base import Model

class SCPRollingResistanceModel(Model):
    def __init__(self): 
        pass

    def update(self, params: Dict[str, float]):
        # TODO
        params['total_mu'] = params['mu'] + params['mu2'] * params['velocity']
        params['rolling_resistance'] = params['normal_force'] * params['total_mu']
        pass
