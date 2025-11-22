from abc import ABC, abstractmethod

class Model(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update(self, params: dict[str, float]):
        pass

class VehicleModel:
    def __init__(self, init_params: dict[str, float]):
        self.models : list[Model] = []
        self.params : dict[str, float] = init_params.copy()

    def add_model(self, model: Model):
        self.models.append(model)

    def update(self):
        for m in self.models:
            m.update(self.params)

    def print_params(self):
        for k,p in self.params.items():
            print(k, p)
