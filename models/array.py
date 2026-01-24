from __future__ import annotations

import math
from datetime import timedelta
from typing import cast, override

from pint.facets.plain import PlainQuantity

from units import Q_
from models.energy_model import EnergyModel


# Array model with:
# 1) geometric incidence factor (sun height proxy)
# 2) lamination optics transmittance tau(theta)
# 3) thermal efficiency derate (cell temperature -> efficiency hit)
class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    # --- SUN / GEOMETRY -------------------------------------------------
    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        # sun height proxy based on latitude and time-of-day.
        # It returns sin(alpha) in [0,1], where alpha is solar altitude.
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since local midnight (assumed)

        lat = math.radians(float(lat_deg))
        time_of_day_hours = float(timestamp) / 3600.0
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)  # hour angle

        # Placeholder declination (upgrade later if you add day-of-year)
        dec = 0.0

        sin_alpha = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(h)
        sin_alpha = max(-1.0, min(1.0, float(sin_alpha)))

        return 0.0 if sin_alpha <= 0 else sin_alpha

    # LAMINATION OPTICS 
    def _tau_theta(self, theta: float, params: dict[str, PlainQuantity[float]]) -> float:
        # Optics-only lamination transmittance multiplier tau(theta) in [0,1]

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
        R *= (1.0 - ar_gain)

        T_interface = max(0.0, 1.0 - R)

        # Beer–Lambert absorption (path length increases by 1/cos(theta1))
        t_cover = float(params["t_cover"].to("meter").magnitude)
        a_cover = float(params["alpha_cover"].to("1/meter").magnitude)
        t_eva = float(params["t_eva"].to("meter").magnitude)
        a_eva = float(params["alpha_eva"].to("1/meter").magnitude)

        path_scale = 1.0 / max(1e-6, float(c1))
        T_abs = math.exp(-a_cover * t_cover * path_scale) * math.exp(-a_eva * t_eva * path_scale)

        tau_misc = float(params["tau_misc"].magnitude) if "tau_misc" in params else 1.0
        tau = T_interface * T_abs * tau_misc

        return max(0.0, min(1.0, float(tau)))

    # THERMAL
    def _irradiance_from_base(self, params: dict[str, PlainQuantity[float]]) -> PlainQuantity[float]:
        
        # don't currently have irradiance (W/m^2) in params.yaml.
        #So we back-calculate an "effective irradiance" from base electrical power:
         
        A = params["array_area"].to("meter^2")
        eff = params["cell_efficiency"]
        # Guard against divide by zero
        eff_mag = float(eff.magnitude)
        if eff_mag <= 0:
            return Q_(0.0, "W/m^2")

        P_base = params["num_cells"] * params["p_mpp"] * eff  # has units of W (assuming p_mpp is W)
        G = P_base / (A * eff)  # W / (m^2) = W/m^2
        return cast(PlainQuantity[float], G.to("W/m^2"))

    def _cell_temperature(self, params: dict[str, PlainQuantity[float]], G: PlainQuantity[float]) -> PlainQuantity[float]:
        # Simple NOCT model for cell temperature (degC)
        T_amb = params["ambient_temp"].to("degC")
        noct = params["noct"].to("degC")
        T_cell = T_amb + (noct - Q_(20.0, "degC")) * (G / Q_(800.0, "W/m^2"))
        return cast(PlainQuantity[float], T_cell.to("degC"))

    def _thermal_factor(self, params: dict[str, PlainQuantity[float]], T_cell: PlainQuantity[float]) -> float:
        
        beta = float(params["temp_coeff"].to("1/degC").magnitude)
        T_ref = params["t_ref"].to("degC")
        dT = float((T_cell - T_ref).to("degC").magnitude)
        return max(0.0, 1.0 - beta * dT)

    @override
    def update(
        self,
        params: dict[str, PlainQuantity[float]],
        timestep: object,  # upstream might pass Pint quantity or datetime.timedelta
    ) -> PlainQuantity[float]:
        inc = self._incidence_factor(params)

        # Base electrical power (before incidence/optics/thermal)
        base_power = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]

        # Normalize timestep to seconds quantity
        if isinstance(timestep, timedelta):
            timestep_s: PlainQuantity[float] = Q_(float(timestep.total_seconds()), "s")
        else:
            timestep_s = cast(PlainQuantity[float], timestep).to("second")

        # Nighttime / no sun
        if inc <= 0.0:
            params["array_power"] = 0.0 * base_power
            energy0 = cast(PlainQuantity[float], params["array_power"] * timestep_s)
            params["array_energy"] = energy0
            return energy0

        # Incidence angle (rad) from incidence factor
        theta = math.acos(max(0.0, min(1.0, inc)))

        # Optics: lamination transmittance multiplier
        tau = self._tau_theta(theta, params)
        tau_q = cast(PlainQuantity[float], Q_(tau, ""))  # dimensionless

        # Thermal: compute T_cell and thermal_factor 
        # do NOT currently have irradiance in params, so we back-calc it from base power.

        G = self._irradiance_from_base(params)  # W/m^2
        T_cell = self._cell_temperature(params, G)  # degC
        f_T = self._thermal_factor(params, T_cell)  # scalar
        f_T_q = cast(PlainQuantity[float], Q_(f_T, ""))

        # Power including incidence, optics, and thermal derate
        params["array_power"] = base_power * inc * tau_q * f_T_q

        energy = cast(PlainQuantity[float], params["array_power"] * timestep_s)
        params["array_energy"] = energy

        # Accumulate total array energy (avoid "+=" to keep pyright calm)
        total_prev = cast(PlainQuantity[float], params["total_array_energy"])
        params["total_array_energy"] = cast(PlainQuantity[float], total_prev + energy)

        # Debug outputs
        params["tau"] = tau_q
        params["theta_rad"] = cast(PlainQuantity[float], Q_(theta, "rad"))
        params["irradiance"] = cast(PlainQuantity[float], G)
        params["cell_temp"] = cast(PlainQuantity[float], T_cell)
        params["thermal_factor"] = f_T_q

        return energy
