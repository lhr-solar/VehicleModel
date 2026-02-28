from models.energy_model import EnergyModel
from typing import override, cast
from pint.facets.plain import PlainQuantity
from pint import Quantity


# A rolling resistance model for an individual wheel
class SCPRollingResistanceModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        precipitation = params.get("weather_precipitation")
        if precipitation is not None:
            clamped = min(precipitation.magnitude, 5.0)
            road_modifier = 1.0 + (clamped / 5.0) * 0.2
            mu_rr_effective = params["mu_rr"] * road_modifier
        else:
            mu_rr_effective = params["mu_rr"]

        # TODO
        params["total_mu"] = cast(
            PlainQuantity[float],
            mu_rr_effective + params["mu2_rr"] * params["velocity"],
        )

        params["f_normal_force"] = (params["f_wheel_weight"] * params["grav_accel"]).to(
            "N"
        )
        params["f_rr_force"] = params["f_normal_force"] * params["total_mu"]
        params["f_rr_power"] = -(params["f_rr_force"] * params["velocity"]).to("watts")

        params["r_normal_force"] = (params["r_wheel_weight"] * params["grav_accel"]).to(
            "N"
        )
        params["r_rr_force"] = params["r_normal_force"] * params["total_mu"]
        params["r_rr_power"] = -(params["r_rr_force"] * params["velocity"]).to("watts")

        params["rr_power"] = cast(
            PlainQuantity[float], 2 * params["f_rr_power"] + params["r_rr_power"]
        )

        return (params["rr_power"] * timestep).to("Wh")
