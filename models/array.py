from __future__ import annotations

import math
from datetime import timedelta
from typing import Protocol, cast, override

from pint.facets.plain import PlainQuantity

from units import Q_
from models.energy_model import EnergyModel



# just making timestep become seconds in one place so i do not repeat myself 80 times
def _normalize_timestep_seconds(timestep: object) -> PlainQuantity[float]:
    if isinstance(timestep, timedelta):
        return Q_(float(timestep.total_seconds()), "s")
    return cast(PlainQuantity[float], timestep).to("second")


# this is the "main" array power model interface
# aka choose how base power is computed: Basic or Irradiance
class ArrayPowerCore(Protocol):
    def compute_power(self, params: dict[str, PlainQuantity[float]]) -> PlainQuantity[float]:
        ...


# this is for optional add-ons like dirt / lamination / thermal
# each one takes the current power and modifies it
class ArrayPowerModifier(Protocol):
    def apply(
        self,
        power: PlainQuantity[float],
        params: dict[str, PlainQuantity[float]],
    ) -> PlainQuantity[float]:
        ...


class BasicArrayCore:
    """
    Super simple electrical/nameplate model.
    Uses num_cells * p_mpp.

    NOTE:
    p_mpp is already electrical power per cell, so do NOT multiply
    by cell_efficiency here or it would be double-counting.
    """

    def compute_power(self, params: dict[str, PlainQuantity[float]]) -> PlainQuantity[float]:
        return cast(PlainQuantity[float], (params["num_cells"] * params["p_mpp"]).to("W"))


class IrradianceArrayCore:
    """
    Simple physics model:
        P = G * A * eta * mppt

    """

    def compute_power(self, params: dict[str, PlainQuantity[float]]) -> PlainQuantity[float]:
        # if something upstream gives me irradiance directly, use it
        if "irradiance" in params:
            G = params["irradiance"].to("W/m^2")
        else:
            # otherwise just use the yaml param directly
            G = params["irradiance_clears"].to("W/m^2")

        A = params["array_area"].to("m^2")
        eta = params["cell_efficiency"]  # dimensionless
        mppt = params.get("mppt_efficiency", Q_(1.0, ""))

        # saving this so debugging is less annoying
        params["irradiance_used"] = cast(PlainQuantity[float], G)

        return cast(PlainQuantity[float], (G * A * eta * mppt).to("W"))


class DirtModifier:
    """
    Simple dirt loss.
    Example:
      dirt_factor = 0.97  means keep 97% of the power
      dirt_factor = 1.00  means basically no dirt loss
    """

    def apply(
        self,
        power: PlainQuantity[float],
        params: dict[str, PlainQuantity[float]],
    ) -> PlainQuantity[float]:
        dirt = params.get("dirt_factor", Q_(1.0, ""))
        params["dirt_factor_used"] = cast(PlainQuantity[float], dirt)
        return cast(PlainQuantity[float], (power * dirt).to("W"))


class LaminationModifier:
    """
    Handles lamination optics stuff.

    This includes:
      - simple sun-height / incidence proxy
      - theta from incidence
      - Fresnel reflection
      - Beer-Lambert absorption through cover + EVA
      - misc transmission losses

    This is separate now so I can use it with Basic OR Irradiance.
    """

    def _incidence_factor(self, params: dict[str, PlainQuantity[float]]) -> float:
        lat_deg = params["latitude_deg"].to("degree").magnitude
        timestamp = params["timestamp"].to("second").magnitude  # seconds since midnight

        lat = math.radians(float(lat_deg))
        time_of_day_hours = float(timestamp) / 3600.0
        h = (time_of_day_hours - 12.0) * (math.pi / 12.0)  # hour angle

        # keeping this simple for now: equinox placeholder declination
        dec = 0.0

        sin_alpha = (
            math.sin(lat) * math.sin(dec)
            + math.cos(lat) * math.cos(dec) * math.cos(h)
        )
        sin_alpha = max(-1.0, min(1.0, float(sin_alpha)))

        # if sun is below horizon then no useful incidence
        return 0.0 if sin_alpha <= 0.0 else float(sin_alpha)

    def _tau_theta(self, theta: float, params: dict[str, PlainQuantity[float]]) -> float:
        n0 = 1.0
        n1 = float(params["n_cover"].magnitude)

        # Snell's law
        s = math.sin(theta) / n1
        s = max(-1.0, min(1.0, s))
        theta1 = math.asin(s)

        c0 = math.cos(theta)
        c1 = math.cos(theta1)

        # Fresnel reflection for unpolarized light
        Rs = ((n0 * c0 - n1 * c1) / (n0 * c0 + n1 * c1)) ** 2
        Rp = ((n0 * c1 - n1 * c0) / (n0 * c1 + n1 * c0)) ** 2
        R = 0.5 * (Rs + Rp)

        # optional AR coating gain lowers reflectance a bit
        ar_gain = float(params["ar_gain"].magnitude) if "ar_gain" in params else 0.0
        R *= (1.0 - ar_gain)
        T_interface = max(0.0, 1.0 - R)

        # Beer-Lambert absorption through the cover stack
        t_cover = float(params["t_cover"].to("meter").magnitude)
        a_cover = float(params["alpha_cover"].to("1/meter").magnitude)
        t_eva = float(params["t_eva"].to("meter").magnitude)
        a_eva = float(params["alpha_eva"].to("1/meter").magnitude)

        # angled rays travel farther through the material
        path_scale = 1.0 / max(1e-6, float(c1))

        T_abs = (
            math.exp(-a_cover * t_cover * path_scale)
            * math.exp(-a_eva * t_eva * path_scale)
        )

        tau_misc = float(params["tau_misc"].magnitude) if "tau_misc" in params else 1.0

        tau = T_interface * T_abs * tau_misc
        return max(0.0, min(1.0, float(tau)))

    def apply(
        self,
        power: PlainQuantity[float],
        params: dict[str, PlainQuantity[float]],
    ) -> PlainQuantity[float]:
        inc = self._incidence_factor(params)

        # if it is basically nighttime, just kill the power here
        if inc <= 0.0:
            params["tau"] = Q_(0.0, "")
            params["theta_rad"] = Q_(math.pi / 2.0, "rad")
            params["incidence_factor"] = Q_(0.0, "")
            return cast(PlainQuantity[float], Q_(0.0, "W"))

        # convert incidence proxy into an angle for optics
        theta = math.acos(max(0.0, min(1.0, inc)))

        tau = self._tau_theta(theta, params)
        tau_q = cast(PlainQuantity[float], Q_(tau, ""))

        # saving debug values bc otherwise i will forget what happened
        params["tau"] = tau_q
        params["theta_rad"] = cast(PlainQuantity[float], Q_(theta, "rad"))
        params["incidence_factor"] = cast(PlainQuantity[float], Q_(inc, ""))

        return cast(PlainQuantity[float], (power * tau_q).to("W"))


class ThermalModifier:
    """
    Handles thermal derate only.

    Uses a simple NOCT-style estimate for cell temperature, then derates power.
    """

    def _get_irradiance_for_thermal(
        self, params: dict[str, PlainQuantity[float]]
    ) -> PlainQuantity[float]:
        if "irradiance" in params:
            return cast(PlainQuantity[float], params["irradiance"].to("W/m^2"))

        return cast(PlainQuantity[float], params["irradiance_clears"].to("W/m^2"))

    def _cell_temperature(
        self, params: dict[str, PlainQuantity[float]], G: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        T_amb = params["ambient_temp"].to("degC")
        noct = params["noct"].to("degC")

        # simple NOCT model
        # T_cell = T_amb + (NOCT - 20C) * (G / 800)
        T_cell = T_amb + (noct - Q_(20.0, "degC")) * (G / Q_(800.0, "W/m^2"))
        return cast(PlainQuantity[float], T_cell.to("degC"))

    def _thermal_factor(
        self, params: dict[str, PlainQuantity[float]], T_cell: PlainQuantity[float]
    ) -> float:
        beta = float(params["temp_coeff"].to("1/degC").magnitude)
        T_ref = params["t_ref"].to("degC")
        dT = float((T_cell - T_ref).to("delta_degC").magnitude)

        # clamp at zero so power never goes negative
        return max(0.0, 1.0 - beta * dT)

    def apply(
        self,
        power: PlainQuantity[float],
        params: dict[str, PlainQuantity[float]],
    ) -> PlainQuantity[float]:
        G = self._get_irradiance_for_thermal(params)
        T_cell = self._cell_temperature(params, G)

        f_T = self._thermal_factor(params, T_cell)
        f_T_q = cast(PlainQuantity[float], Q_(f_T, ""))

        params["cell_temp"] = cast(PlainQuantity[float], T_cell)
        params["thermal_factor"] = f_T_q

        return cast(PlainQuantity[float], (power * f_T_q).to("W"))


class ComposedArrayModel(EnergyModel):
    """
    Flexible array model.

    Pick one core:
      - BasicArrayCore()
      - IrradianceArrayCore()

    Then stack whatever modifiers you want:
      - DirtModifier()
      - LaminationModifier()
      - ThermalModifier()

    So now Basic vs Irradiance is separate from whether I want dirt/lamination/etc.
    which is kinda the whole point.
    """

    def __init__(
        self,
        core: ArrayPowerCore,
        modifiers: list[ArrayPowerModifier] | None = None,
    ):
        self.core = core
        self.modifiers = modifiers or []

    @override
    def update(
        self,
        params: dict[str, PlainQuantity[float]],
        timestep: object,
    ) -> PlainQuantity[float]:
        timestep_s = _normalize_timestep_seconds(timestep)

        # step 1: get base power from the core model
        power = self.core.compute_power(params)

        # step 2: run optional modifiers one by one
        for modifier in self.modifiers:
            power = modifier.apply(power, params)

        # step 3: same bookkeeping as before
        params["array_power"] = cast(PlainQuantity[float], power.to("W"))

        energy = cast(PlainQuantity[float], params["array_power"] * timestep_s)
        params["array_energy"] = energy
        params["total_array_energy"] = cast(
            PlainQuantity[float], params["total_array_energy"] + energy
        )

        return energy


# keeping these wrapper names so usage still feels normal
class BasicArrayModel(ComposedArrayModel):
    """
    Backward-friendly BasicArrayModel.
    Default = just basic power unless I add modifiers.
    """

    def __init__(self, modifiers: list[ArrayPowerModifier] | None = None):
        super().__init__(core=BasicArrayCore(), modifiers=modifiers)


class IrradianceArrayModel(ComposedArrayModel):
    """
    Backward-friendly IrradianceArrayModel.
    Default = just irradiance power unless I add modifiers.
    """

    def __init__(self, modifiers: list[ArrayPowerModifier] | None = None):
        super().__init__(core=IrradianceArrayCore(), modifiers=modifiers)

 ## Example how to use in main
'''
i want all three modifiers, but i want to use the irradiance core, so:
 model = IrradianceArrayModel(
    modifiers=[
        DirtModifier(),
        LaminationModifier(),
        ThermalModifier(),
    ]
)'''