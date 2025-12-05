from models.base import Model
from typing import override
from .esr_loss_model import ESRBatteryLossModel

class SCPBatteryModel(Model):

    def __init__(self):
        super().__init__()
        #esr_loss
        self.loss_model = ESRBatteryLossModel()
    
    @override
    def update(self, params: dict[str, float]):
        # TODO
        self.loss_model.update(params)
        #may need to reset current each time we update to grab the new instant value
        #params['current_draw'] = 0.0
        
