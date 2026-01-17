from typing import override, cast
from pint.facets.plain import PlainQuantity
from pint import Quantity
from units import Q_
import math
# Optics-only model: accounts only for lamination light losses (reflection + absorption + dirt), ignoring all thermal effects.

  class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    def _incidence_factor(self, params: dict[str, Quantity]) -> float:
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude

        lat = math.radians(lat_deg)
        time_of_day_hours = timestamp / 3600.0
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)
        dec = 0.0

        sin_alpha = (
            math.sin(lat) * math.sin(dec) +
            math.cos(lat) * math.cos(dec) * math.cos(h)
        )
        sin_alpha = max(-1.0, min(1.0, sin_alpha))

        return 0.0 if sin_alpha <= 0 else sin_alpha

    def _tau_theta(self, theta: float, params: dict[str, Quantity]) -> float:
        # Optics-only lamination transmittance

        n0 = 1.0
        n1 = float(params["n_cover"].magnitude)

        # Snell
        s = math.sin(theta) / n1
        s = max(-1.0, min(1.0, s))
        theta1 = math.asin(s)

        c0 = math.cos(theta)
        c1 = math.cos(theta1)

        # Fresnel (unpolarized)
        Rs = ((n0 * c0 - n1 * c1) / (n0 * c0 + n1 * c1)) ** 2
        Rp = ((n0 * c1 - n1 * c0) / (n0 * c1 + n1 * c0)) ** 2
        R = 0.5 * (Rs + Rp)

        ar_gain = float(params["ar_gain"].magnitude) if "ar_gain" in params else 0.0
        R *= (1.0 - ar_gain)

        T_interface = max(0.0, 1.0 - R)

        # Beer–Lambert absorption (path length increases by 1/cos(theta1))
        t_cover = params["t_cover"].to("meter").magnitude
        a_cover = params["alpha_cover"].to("1/meter").magnitude
        t_eva = params["t_eva"].to("meter").magnitude
        a_eva = params["alpha_eva"].to("1/meter").magnitude

        path_scale = 1.0 / max(1e-6, c1)
        T_abs = math.exp(-a_cover * t_cover * path_scale) * math.exp(-a_eva * t_eva * path_scale)

        tau_misc = float(params["tau_misc"].magnitude)
        tau = T_interface * T_abs * tau_misc

        return max(0.0, min(1.0, tau))

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
      inc = self._incidence_factor(params)

        base_power = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]

        if inc <= 0.0:
            params["array_power"] = 0.0 * base_power
            params["array_energy"] = params["array_power"] * timestep
            return params["array_energy"]

        # Convert incidence angle for optics
        theta = math.acos(max(0.0, min(1.0, inc)))

        # Lamination transmittance multiplier
        tau = self._tau_theta(theta, params)

        # AFTER: include tau
        params["array_power"] = base_power * inc * tau

        params["array_energy"] = params["array_power"] * timestep
        params["total_array_energy"] += params["array_energy"]

        # Optional debug outputs 
        params["tau"] = tau
        params["theta_rad"] = theta

        return params["array_energy"]
