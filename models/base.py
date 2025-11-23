from abc import ABC, abstractmethod
from pint import Quantity

class EnergyModel(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        pass

class VehicleModel:
    def __init__(self, init_params: dict[str, Quantity[float]]):
        self.models : list[EnergyModel] = []
        self.params : dict[str, Quantity[float]] = init_params.copy()

    def add_model(self, model: EnergyModel):
        self.models.append(model)

    def update(self):
        self.prev_params = self.params.copy()
        for m in self.models:
            self.params['total_energy'] += m.update(self.params, self.params['timestep'])

    def print_params(self):
        for k,p in self.params.items():
            print(k, p)

    def print_params_diff(self):
        for k,p in self.params.items():
            if k not in self.prev_params: print(k, p)
            else: 
                if self.prev_params[k] != self.params[k]: print(k, p)
