from abc import ABC, abstractmethod
from pint.facets.plain import PlainQuantity
from pint import Quantity
from datetime import datetime

class EnergyModel(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update(self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]) -> PlainQuantity[float]:
        pass

class VehicleModel:
    def __init__(self, init_params: dict[str, PlainQuantity[float]]):
        self.models : list[EnergyModel] = []
        self.params : dict[str, PlainQuantity[float]] = init_params.copy()

    def add_model(self, model: EnergyModel):
        self.models.append(model)

    def update(self):
        self.prev_params = self.params.copy()
        for m in self.models:
            self.params['total_energy'] += m.update(self.params, self.params['timestep'])

    def print_params(self):
        for k,p in self.params.items():
            print(k, p)
