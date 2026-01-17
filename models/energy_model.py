from abc import ABC, abstractmethod
from pint import Quantity

class EnergyModel(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        pass

