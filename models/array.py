from __future__ import annotations

import math
from datetime import timedelta
from typing import cast, override

from pint.facets.plain import PlainQuantity

from units import Q_

from models.energy_model import EnergyModel


# Optics-only model: accounts only for lamination light losses (reflection + absorption + dirt),
# ignoring all thermal effects.
# lamination transmittance: use tau_theta: given sun angle, how much light makes it thru lamination. models reflection at air/glass interface/ optional anti reflection coating which we dk yet because it is based on the material we are acc using, and absorption in glass (beer-lamber law)
class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude

        lat = math.radians(lat_deg)
        time_of_day_hours = float(timestamp) / 3600.0
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)

        # Placeholder declination (replace later if add a real solar declination model)
        dec = 0.0

        sin_alpha = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(
            dec
        ) * math.cos(h)
        sin_alpha = max(-1.0, min(1.0, sin_alpha))

        return 0.0 if sin_alpha <= 0 else sin_alpha

    def _tau_theta(
        self, theta: float, params: dict[str, PlainQuantity[float]]
    ) -> float:
        # Optics-only lamination transmittance multiplier tau(theta) in [0,1].

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

        # Optional AR boost reduces reflectance
        ar_gain = float(params["ar_gain"].magnitude) if "ar_gain" in params else 0.0
        R *= 1.0 - ar_gain

        T_interface = max(0.0, 1.0 - R)

        # Beer–Lambert absorption (path length increases by 1/cos(theta1))
        t_cover = params["t_cover"].to("meter").magnitude
        a_cover = params["alpha_cover"].to("1/meter").magnitude
        t_eva = params["t_eva"].to("meter").magnitude
        a_eva = params["alpha_eva"].to("1/meter").magnitude

        path_scale = 1.0 / max(1e-6, c1)
        T_abs = math.exp(-a_cover * t_cover * path_scale) * math.exp(
            -a_eva * t_eva * path_scale
        )

        tau_misc = float(params["tau_misc"].magnitude) if "tau_misc" in params else 1.0
        tau = T_interface * T_abs * tau_misc

        return max(0.0, min(1.0, tau))

    @override
    def update(
        self,
        params: dict[str, PlainQuantity[float]],
        timestep: object,
    ) -> PlainQuantity[float]:
        # We intentionally accept `timestep` as `object` because upstream code may pass
        # either a Pint quantity or a datetime.timedelta.

        inc = self._incidence_factor(params)

        # Define base_power early (prevents "possibly unbound" warnings)
        base_power = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]

        # Normalize timestep to a Pint quantity in seconds
        if isinstance(timestep, timedelta):
            timestep_s: PlainQuantity[float] = Q_(float(timestep.total_seconds()), "s")
        else:
            timestep_s = cast(PlainQuantity[float], timestep).to("second")

        if inc <= 0.0:
            params["array_power"] = 0.0 * base_power
            energy0 = cast(PlainQuantity[float], params["array_power"] * timestep_s)
            params["array_energy"] = energy0
            return energy0

        # Convert incidence factor to an incidence angle
        theta = math.acos(max(0.0, min(1.0, inc)))

        # Lamination transmittance multiplier
        tau = self._tau_theta(theta, params)
        tau_q = cast(PlainQuantity[float], Q_(tau, ""))  # dimensionless

        # Include tau (lamination losses)
        params["array_power"] = base_power * inc * tau_q

        energy = cast(PlainQuantity[float], params["array_power"] * timestep_s)
        params["array_energy"] = energy

        # Avoid "+=" on a dict value (Pyright treats read as Unknown). Do a casted set.
        total_prev = cast(PlainQuantity[float], params["total_array_energy"])
        params["total_array_energy"] = cast(PlainQuantity[float], total_prev + energy)

        # debug outputs
        params["tau"] = tau_q
        params["theta_rad"] = cast(PlainQuantity[float], Q_(theta, "rad"))

        return energy
