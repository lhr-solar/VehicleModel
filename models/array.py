from models.base import Model
from typing import override

class SCPArrayModel(Model):
    def __init__(self):
        super().__init__()

    @override
    def update(self, params: dict[str, float]):
        params["array_power"] = params["num_cells"] * params["p_mpp"]
        params["total_power"] += params["array_power"]
