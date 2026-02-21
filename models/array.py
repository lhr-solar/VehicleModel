from __future__ import annotations

import math
from datetime import timedelta
from typing import cast, override

from pint.facets.plain import PlainQuantity

from units import Q_
from models.energy_model import EnergyModel


class BasicArrayModel(EnergyModel):
    """
    Electrical-nameplate model. Uses num_cells * p_mpp.
    NOTE: p_mpp is assumed to already be electrical max power per cell (W/cell),
    so we do NOT multiply by cell_efficiency here.
    """
    @override
    def update(self, params, timestep):
        # Normalize timestep to seconds quantity
        if isinstance(timestep, timedelta):
            timestep_s: PlainQuantity[float] = Q_(float(timestep.total_seconds()), "s")
        else:
            timestep_s = cast(PlainQuantity[float], timestep).to("second")

        params["array_power"] = cast(
            PlainQuantity[float], (params["num_cells"] * params["p_mpp"]).to("W")
        )
        energy = cast(PlainQuantity[float], params["array_power"] * timestep_s)
        params["array_energy"] = energy
        params["total_array_energy"] = cast(
            PlainQuantity[float], params["total_array_energy"] + energy
        )
        return energy


class IrradianceArrayModel(EnergyModel):
    """
    Simple physics model: P = G * A * eta * mppt
    If params["irradiance"] exists, uses it.
    Otherwise falls back to irradiance_clear/irradiance_clears (YAML typo-safe).
    """
    @override
    def update(self, params, timestep):
        if isinstance(timestep, timedelta):
            timestep_s: PlainQuantity[float] = Q_(float(timestep.total_seconds()), "s")
        else:
            timestep_s = cast(PlainQuantity[float], timestep).to("second")

        # Use measured irradiance if upstream sets it
        if "irradiance" in params:
            G = params["irradiance"].to("W/m^2")
        else:
            # typo-safe fallback: irradiance_clear OR irradiance_clears OR default
            G = cast(
                PlainQuantity[float],
                params.get(
                    "irradiance_clear",
                    params.get("irradiance_clears", Q_(1000.0, "W/m^2")),
                ).to("W/m^2"),
            )

        A = params["array_area"].to("m^2")
        eta = params["cell_efficiency"]  # dimensionless
        mppt = params.get("mppt_efficiency", Q_(1.0, ""))

        params["array_power"] = cast(PlainQuantity[float], (G * A * eta * mppt).to("W"))
        energy = cast(PlainQuantity[float], params["array_power"] * timestep_s)
        params["array_energy"] = energy
        params["total_array_energy"] = cast(
            PlainQuantity[float], params["total_array_energy"] + energy
        )
        return energy


class SCPArrayModelLamination(EnergyModel):
    """
      - sun height proxy (inc in [0,1])
      - lamination optics tau(theta)
      - thermal derate from NOCT
      - mppt efficiency
      - irradiance source: measured params["irradiance"] if present,
        else clear-sky peak scaled by inc
    Power:
      P = G * A * eta * tau(theta) * f_T * mppt
    """

    # SUN / GEOMETRY
    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        lat = math.radians(float(lat_deg))
        time_of_day_hours = float(timestamp) / 3600.0
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)  # hour angle

        # Placeholder declination (equinox). Good enough for “simple + causal”.
        dec = 0.0

        sin_alpha = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(h)
        sin_alpha = max(-1.0, min(1.0, float(sin_alpha)))

        return 0.0 if sin_alpha <= 0 else float(sin_alpha)

    # LAMINATION OPTICS
    def _tau_theta(self, theta: float, params: dict[str, PlainQuantity[float]]) -> float:
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
    def _cell_temperature(
        self, params: dict[str, PlainQuantity[float]], G: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        T_amb = params["ambient_temp"].to("degC")
        noct = params["noct"].to("degC")
        # NOCT model: T_cell = T_amb + (NOCT-20C) * (G/800)
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
        timestep: object,
    ) -> PlainQuantity[float]:
        inc = self._incidence_factor(params)

        # Normalize timestep to seconds
        if isinstance(timestep, timedelta):
            timestep_s: PlainQuantity[float] = Q_(float(timestep.total_seconds()), "s")
        else:
            timestep_s = cast(PlainQuantity[float], timestep).to("second")

        # Nighttime
        if inc <= 0.0:
            params["array_power"] = Q_(0.0, "W")
            energy0 = cast(PlainQuantity[float], params["array_power"] * timestep_s)
            params["array_energy"] = energy0
            params["total_array_energy"] = cast(
                PlainQuantity[float], params["total_array_energy"] + energy0
            )
            return energy0

        # Convert inc->theta (rad) for optics
        theta = math.acos(max(0.0, min(1.0, inc)))

        # tau(theta)
        tau = self._tau_theta(theta, params)
        tau_q = cast(PlainQuantity[float], Q_(tau, ""))

        # Irradiance source:
        #  - if measured irradiance exists, use it directly (assume POA)
        #  - else use clear-sky peak scaled by inc (simple sun-height proxy)
        if "irradiance" in params:
            G = params["irradiance"].to("W/m^2")
            G_src = "measured"
        else:
            G_clear = cast(
                PlainQuantity[float],
                params.get(
                    "irradiance_clear",
                    params.get("irradiance_clears", Q_(1000.0, "W/m^2")),
                ).to("W/m^2"),
            )
            G = cast(PlainQuantity[float], (G_clear * Q_(inc, "")).to("W/m^2"))
            G_src = "clear*inc"

        # Thermal derate
        T_cell = self._cell_temperature(params, G)
        f_T = self._thermal_factor(params, T_cell)
        f_T_q = cast(PlainQuantity[float], Q_(f_T, ""))

        # MPPT
        mppt = params.get("mppt_efficiency", Q_(1.0, ""))

        # Power
        A = params["array_area"].to("m^2")
        eta = params["cell_efficiency"]  # dimensionless
        params["array_power"] = cast(
            PlainQuantity[float], (G * A * eta * tau_q * f_T_q * mppt).to("W")
        )

        energy = cast(PlainQuantity[float], params["array_power"] * timestep_s)
        params["array_energy"] = energy
        params["total_array_energy"] = cast(
            PlainQuantity[float], params["total_array_energy"] + energy
        )

        # Debug outputs
        params["tau"] = tau_q
        params["theta_rad"] = cast(PlainQuantity[float], Q_(theta, "rad"))
        params["irradiance"] = cast(PlainQuantity[float], G)  # store what we used
        params["irradiance_source"] = Q_(1.0, "")  # placeholder to keep type consistent if needed
        params["cell_temp"] = cast(PlainQuantity[float], T_cell)
        params["thermal_factor"] = f_T_q
        params["incidence_factor"] = cast(PlainQuantity[float], Q_(inc, ""))

        return energy