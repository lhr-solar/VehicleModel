from abc import ABC, abstractmethod
import numpy as np
from pint.facets.plain import PlainQuantity


class EnergyModel(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update_dynamic(
        self,
        params: dict[str, PlainQuantity[float]],
        velocities_si: np.ndarray,
        sub_dt: float,
    ) -> PlainQuantity[float]:
        pass
