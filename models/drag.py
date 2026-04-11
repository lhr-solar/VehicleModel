import numpy as np
from models.energy_model import EnergyModel
from typing import override
from pint.facets.plain import PlainQuantity
from pint import Quantity
from units import Q_


class SCPDragModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @staticmethod
    def _wind_modifier_vec(
        wind_speed: float,
        wind_direction: float,
        vehicle_heading: float,
        vehicle_speed_arr: np.ndarray,
    ) -> np.ndarray:
        headwind = wind_speed * np.cos(
            np.radians((wind_direction - vehicle_heading) % 360)
        )
        relative_speed = np.maximum(vehicle_speed_arr + headwind, 0.0)
        return np.where(
            vehicle_speed_arr > 0.0,
            (relative_speed / vehicle_speed_arr) ** 2,
            1.0,
        )

    @override
    def update_dynamic(
        self,
        params: dict[str, PlainQuantity[float]],
        velocities_si: np.ndarray,
        sub_dt: float,
    ) -> PlainQuantity[float]:
        v = velocities_si  # m/s, shape (n,)

        wind_speed = (
            params.get("weather_wind_speed", Quantity(0, "m/s")).to("m/s").magnitude
        )
        wind_direction = params.get(
            "weather_wind_direction", Quantity(0, "degree")
        ).magnitude
        vehicle_heading = params.get("vehicle_heading", Quantity(0, "degree")).magnitude

        wind_modifier = self._wind_modifier_vec(
            wind_speed, wind_direction, vehicle_heading, v
        )

        rho = params["air_density"].to("kg/m^3").magnitude
        Cd = params["drag_coeff"].magnitude
        A = params["frontal_area"].to("m^2").magnitude

        drag_power_vec = 0.5 * rho * Cd * A * wind_modifier * v**3  # W, shape (n,)

        # Store time-averaged scalar for logging and battery model
        params["drag_power"] = Q_(float(-np.mean(drag_power_vec)), "W")

        # Store power vector for motor model (inter-model communication)
        params["_drag_power_vec"] = drag_power_vec  # type: ignore[assignment]

        energy_J = float(np.trapezoid(drag_power_vec, dx=sub_dt))
        return Q_(-energy_J / 3600.0, "Wh")
