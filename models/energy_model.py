from abc import ABC, abstractmethod
from pint.facets.plain import PlainQuantity
from pint import Quantity

class EnergyModel(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update(self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]) -> PlainQuantity[float]:
        pass

