from abc import ABC, abstractmethod
from pint import Quantity
from .battery import BatteryModel
from .energy_model import EnergyModel

class VehicleModel:
    def __init__(self, init_params: dict[str, Quantity[float]]):
        self.battery_model : BatteryModel = None
        self.models : list[EnergyModel] = []
        self.params : dict[str, Quantity[float]] = init_params.copy()

    def add_model(self, model: EnergyModel):
        if isinstance(model, BatteryModel):
            self.battery_model = model
        else:
            self.models.append(model)

    def update(self):
        self.prev_params = self.params.copy()
        for m in self.models:
            self.params['total_energy'] += m.update(self.params, self.params['timestep'])
        #battery update
        self.params['total_energy'] += self.battery_model.update(self.params, self.params['timestep'])
    def print_params(self):
        for k,p in self.params.items():
            print(k, p)
