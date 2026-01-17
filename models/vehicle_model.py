from abc import ABC, abstractmethod
from pint.facets.plain import PlainQuantity
from pint import Quantity
from .battery import BatteryModel
from .energy_model import EnergyModel

class VehicleModel:
    def __init__(self, init_params: dict[str, PlainQuantity[float]]):
        self.battery_model : BatteryModel = BatteryModel()
        self.models : list[EnergyModel] = []
        self.params : dict[str, PlainQuantity[float]] = init_params.copy()

    def add_model(self, model: EnergyModel):
        self.models.append(model)

    def set_battery_model(self, model: BatteryModel):
        self.battery_model = model

    def update(self):
        self.prev_params = self.params.copy()
        for m in self.models:
            self.params['total_energy'] += m.update(self.params, self.params['timestep'])

        self.params['total_energy'] += self.battery_model.update(self.params, self.params['timestep'])

    def print_params(self):
        for k,p in self.params.items():
            print(k, p)
