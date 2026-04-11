import numpy as np
from models.energy_model import EnergyModel
from typing import override
from pint.facets.plain import PlainQuantity
from units import Q_


class ESRBatteryLossModel(EnergyModel):
    def __init__(self):
        pass

    @override
    def update_dynamic(
        self,
        params: dict[str, PlainQuantity[float]],
        velocities_si: np.ndarray,
        sub_dt: float,
    ) -> PlainQuantity[float]:
        outer_timestep = Q_(sub_dt * len(velocities_si), "seconds")

        params["pack_resistance"] = (
            params["cell_internal_impedance"] / params["cells_in_parallel"]
        ) * params["cells_in_series"]

        params["current_draw"] = (params["drag_power"] + params["rr_power"]) / params[
            "battery_voltage_nominal"
        ]
        params["battery_power_loss"] = (params["current_draw"] ** 2) * params[
            "pack_resistance"
        ]
        return -params["battery_power_loss"] * outer_timestep


class BatteryModel(EnergyModel):
    def __init__(self):
        super().__init__()
        self.loss_model = ESRBatteryLossModel()

    @override
    def update_dynamic(
        self,
        params: dict[str, PlainQuantity[float]],
        velocities_si: np.ndarray,
        sub_dt: float,
    ) -> PlainQuantity[float]:
        return self.loss_model.update_dynamic(params, velocities_si, sub_dt)
