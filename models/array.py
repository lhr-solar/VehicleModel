from __future__ import annotations

import math
from datetime import timedelta
from typing import cast, override

from pint.facets.plain import PlainQuantity

from units import Q_
from models.energy_model import EnergyModel

class BasicArrayModel(EnergyModel):
    @override
    def update(self, params, timestep):
        params["array_power"] = params["num_cells"] * params["p_mpp"]
        return params["array_power"] * timestep


class IrradianceArrayModel(EnergyModel):
    @override
    def update(self, params, timestep):
        params["array_power"] = params["irradiance"] * params["array_area"] * params["cell_efficiency"]
        return params["array_power"] * timestep
    
# Array model with:
# 1) geometric incidence factor (sun height proxy)
# 2) lamination optics transmittance tau(theta)
# 3) thermal efficiency derate (cell temperature -> efficiency hit)
class SCPArrayModelLamination(EnergyModel):
    def __init__(self):
        super().__init__()

    # SUN / GEOMETRY
    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        # Returns sin(alpha) in [0,1], where alpha is solar altitude.
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        lat = math.radians(float(lat_deg))
        time_of_day_hours = float(timestamp) / 3600.0
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)  # hour angle

        # Placeholder declination (upgrade later when add day-of-year)
        dec = 0.0

        sin_alpha = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(
            dec
        ) * math.cos(h)
        sin_alpha = max(-1.0, min(1.0, float(sin_alpha)))

        return 0.0 if sin_alpha <= 0 else sin_alpha

    # LAMINATION OPTICS
    def _tau_theta(
        self, theta: float, params: dict[str, PlainQuantity[float]]
    ) -> float:
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
        R *= 1.0 - ar_gain
        T_interface = max(0.0, 1.0 - R)

        # Beer–Lambert absorption (path length increases by 1/cos(theta1))
        t_cover = float(params["t_cover"].to("meter").magnitude)
        a_cover = float(params["alpha_cover"].to("1/meter").magnitude)
        t_eva = float(params["t_eva"].to("meter").magnitude)
        a_eva = float(params["alpha_eva"].to("1/meter").magnitude)

        path_scale = 1.0 / max(1e-6, float(c1))
        T_abs = math.exp(-a_cover * t_cover * path_scale) * math.exp(
            -a_eva * t_eva * path_scale
        )

        tau_misc = float(params["tau_misc"].magnitude) if "tau_misc" in params else 1.0
        tau = T_interface * T_abs * tau_misc

        return max(0.0, min(1.0, float(tau)))

    # THERMAL
    def _cell_temperature(
        self, params: dict[str, PlainQuantity[float]], G: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        # Simple NOCT model for cell temperature (degC)
        T_amb = params["ambient_temp"].to("degC")
        noct = params["noct"].to("degC")
        T_cell = T_amb + (noct - Q_(20.0, "degC")) * (G / Q_(800.0, "W/m^2"))
        return cast(PlainQuantity[float], T_cell.to("degC"))

    def _thermal_factor(
        self, params: dict[str, PlainQuantity[float]], T_cell: PlainQuantity[float]
    ) -> float:
        beta = float(params["temp_coeff"].to("1/degC").magnitude)
        T_ref = params["t_ref"].to("degC")
        dT = float((T_cell - T_ref).to("delta_degC").magnitude)
        return max(0.0, 1.0 - beta * dT)

    @override
    def update(
        self,
        params: dict[str, PlainQuantity[float]],
        timestep: object,  # upstream might pass Pint quantity or datetime.timedelta
    ) -> PlainQuantity[float]:
        inc = self._incidence_factor(params)

        # Normalize timestep to seconds quantity
        if isinstance(timestep, timedelta):
            timestep_s: PlainQuantity[float] = Q_(float(timestep.total_seconds()), "s")
        else:
            timestep_s = cast(PlainQuantity[float], timestep).to("second")

        # Nighttime / no sun
        if inc <= 0.0:
            params["array_power"] = Q_(0.0, "W")
            energy0 = cast(PlainQuantity[float], params["array_power"] * timestep_s)
            params["array_energy"] = energy0
            return energy0

        # Incidence angle (rad) from incidence factor
        theta = math.acos(max(0.0, min(1.0, inc)))

        # Optics: lamination transmittance multiplier
        tau = self._tau_theta(theta, params)
        tau_q = cast(PlainQuantity[float], Q_(tau, ""))  # dimensionless

        # Irradiance model: clear-sky peak scaled by sun height proxy
        # (simple + causal; replace later with measured irradiance)
        G_clear = params.get("irradiance_clear", Q_(1000.0, "W/m^2")).to("W/m^2")
        G = cast(PlainQuantity[float], (G_clear * inc).to("W/m^2"))

        # Thermal: compute T_cell and thermal_factor
        T_cell = self._cell_temperature(params, G)
        f_T = self._thermal_factor(params, T_cell)
        f_T_q = cast(PlainQuantity[float], Q_(f_T, ""))

        # Electrical power from irradiance (direction-correct physics)
        A = params["array_area"].to("m^2")
        eta = params["cell_efficiency"]  # dimensionless
        params["array_power"] = cast(
            PlainQuantity[float], (G * A * eta * tau_q * f_T_q).to("W")
        )

        energy = cast(PlainQuantity[float], params["array_power"] * timestep_s)
        params["array_energy"] = energy

        # Accumulate total array energy
        total_prev = cast(PlainQuantity[float], params["total_array_energy"])
        params["total_array_energy"] = cast(PlainQuantity[float], total_prev + energy)

        # Debug outputs
        params["tau"] = tau_q
        params["theta_rad"] = cast(PlainQuantity[float], Q_(theta, "rad"))
        params["irradiance"] = cast(PlainQuantity[float], G)
        params["cell_temp"] = cast(PlainQuantity[float], T_cell)
        params["thermal_factor"] = f_T_q

        return energy

## BASIC MODEL ONLY SUN ANGLE:
class SCPArrayModel(EnergyModel):
    def __init__(self):
        super().__init__()

    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        # Compute how much sunlight hits the array (0–1)
        # based on time of day + latitude.
       
    
        # Extract raw numbers
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        # Convert latitude to radians
        lat = math.radians(lat_deg)

        # Time of day in seconds 
        time_of_day_s = timestamp

        # Convert to fractional hours for hour angle
        time_of_day_hours = time_of_day_s / 3600.0

        # Hour angle: 0 at noon, now with second-level precision
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)

        # Simple declination (equinox)
        dec = 0.0

        # Solar elevation angle formula from book
        sin_alpha = (
            math.sin(lat) * math.sin(dec) +
            math.cos(lat) * math.cos(dec) * math.cos(h)
        )
        sin_alpha = max(-1.0, min(1.0, sin_alpha))

        if sin_alpha <= 0:
            return 0.0  # sun below horizon → no power

        return sin_alpha

    @override
    def update(self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]) -> PlainQuantity[float]:
        params["array_power"] = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]
        return params["array_power"] * timestep


class SCPArrayModelWithIncidence(EnergyModel):
    def __init__(self):
        super().__init__()

    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        # Compute how much sunlight hits the array (0–1)
        # based on time of day + latitude.
       
    
        # Extract raw numbers
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        # Convert latitude to radians
        lat = math.radians(lat_deg)

        # Time of day in seconds 
        time_of_day_s = timestamp

        # Convert to fractional hours for hour angle
        time_of_day_hours = time_of_day_s / 3600.0

        # Hour angle: 0 at noon, now with second-level precision
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)

        # Simple declination (equinox)
        dec = 0.0

        # Solar elevation angle formula from book
        sin_alpha = (
            math.sin(lat) * math.sin(dec) +
            math.cos(lat) * math.cos(dec) * math.cos(h)
        )
        sin_alpha = max(-1.0, min(1.0, sin_alpha))

        if sin_alpha <= 0:
            return 0.0  # sun below horizon → no power

        return sin_alpha

    @override
    def update(self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]) -> PlainQuantity[float]:
        # Updates array power based on sun angle
        # accumulates energy into total_array_energy.

        # sunlight factor 0–1
        factor = self._incidence_factor(params)

       # base max power
        base_power = params["num_cells"] * params["p_mpp"] * params["cell_efficiency"]

        params["array_power"] = base_power * factor

            # energy produced this timestep (Power × time)
        params["array_energy"] = params["array_power"] * timestep

        # accumulate total array energy over the whole race
        params["total_array_energy"] += params["array_energy"]

        # return energy produced this timestep
        return params["array_energy"]