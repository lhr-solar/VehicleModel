import numpy as np
from models.energy_model import EnergyModel
from typing import override
from pint.facets.plain import PlainQuantity
from units import Q_


class SCPRollingResistanceModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update_dynamic(
        self,
        params: dict[str, PlainQuantity[float]],
        velocities_si: np.ndarray,
        sub_dt: float,
    ) -> PlainQuantity[float]:
        v = velocities_si  # m/s, shape (n,)

        # mu2_rr is in h/km; velocity must be in km/h for dimensionless product
        mu_rr = params["mu_rr"].magnitude
        mu2_rr = params["mu2_rr"].to("h/km").magnitude
        total_mu = mu_rr + mu2_rr * (v * 3.6)  # dimensionless, shape (n,)

        g = params["grav_accel"].to("m/s^2").magnitude
        f_normal = params["f_wheel_weight"].to("kg").magnitude * g  # N, scalar
        r_normal = params["r_wheel_weight"].to("kg").magnitude * g  # N, scalar

        f_rr_power_vec = f_normal * total_mu * v  # W, shape (n,)
        r_rr_power_vec = r_normal * total_mu * v  # W, shape (n,)
        rr_power_vec = 2 * f_rr_power_vec + r_rr_power_vec  # W, shape (n,)

        # Store time-averaged scalars for logging and downstream models
        mean_mu = float(np.mean(total_mu))
        params["total_mu"] = Q_(mean_mu, "dimensionless")
        params["f_normal_force"] = Q_(float(f_normal), "N")
        params["f_rr_force"] = Q_(float(f_normal * mean_mu), "N")
        params["f_rr_power"] = Q_(float(-np.mean(f_rr_power_vec)), "W")
        params["r_normal_force"] = Q_(float(r_normal), "N")
        params["r_rr_force"] = Q_(float(r_normal * mean_mu), "N")
        params["r_rr_power"] = Q_(float(-np.mean(r_rr_power_vec)), "W")
        params["rr_power"] = Q_(float(-np.mean(rr_power_vec)), "W")

        # Store power vector for motor model (inter-model communication)
        params["_rr_power_vec"] = rr_power_vec  # type: ignore[assignment]

        energy_J = float(np.trapezoid(rr_power_vec, dx=sub_dt))
        return Q_(-energy_J / 3600.0, "Wh")
