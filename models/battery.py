from models.energy_model import EnergyModel
from typing import override
from pint.facets.plain import PlainQuantity


class ESRBatteryLossModel(EnergyModel):
    def __init__(self):
        pass

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        # Pack Resistance (increases with temperature)
        base_resistance = (
            params["cell_internal_impedance"] / params["cells_in_parallel"]
        ) * params["cells_in_series"]

        temp = params.get("weather_temperature")
        if temp is not None:
            temperature = temp.to("celsius").magnitude
            temp_modifier = 1.0 + (temperature - 25.0) * -0.005
            params["pack_resistance"] = base_resistance / temp_modifier
        else:
            params["pack_resistance"] = base_resistance

        # P = I^2 * R
        params["current_draw"] = (params["drag_power"] + params["rr_power"]) / params[
            "battery_voltage_nominal"
        ]
        params["battery_power_loss"] = (params["current_draw"] ** 2) * params[
            "pack_resistance"
        ]
        return -params["battery_power_loss"] * timestep


class BatteryModel(EnergyModel):
    def __init__(self):
        super().__init__()
        # esr_loss
        self.loss_model = ESRBatteryLossModel()

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        return self.loss_model.update(params, timestep)
