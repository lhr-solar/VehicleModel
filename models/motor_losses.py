import numpy as np
from typing import override
from pint.facets.plain import PlainQuantity
from models.energy_model import EnergyModel
from units import Q_


class MotorLossModel(EnergyModel):
    def __init__(self):
        super().__init__()

    def _loss_vec(
        self,
        I_arr: np.ndarray,
        N_rpm_arr: np.ndarray,
        params: dict[str, PlainQuantity[float]],
    ) -> np.ndarray:
        """Vectorized motor loss calculation. All inputs/outputs in SI base units (W, A, rpm)."""
        R_A = params["motor_R_A"].to("ohm").magnitude
        R_B = params["motor_R_B"].to("ohm").magnitude
        k_H = params["motor_k_H_default"].magnitude
        k_E = params["motor_k_E_default"].magnitude
        k_B1 = params["motor_k_B1_default"].magnitude
        k_B2 = params["motor_k_B2_default"].magnitude
        k_D = params["motor_k_D_default"].magnitude

        P_copper = (I_arr**2) * (R_A + R_B)
        P_stray = (
            k_H * N_rpm_arr
            + k_E * N_rpm_arr**2
            + (k_B1 + k_B2 * N_rpm_arr) * N_rpm_arr
            + k_D * N_rpm_arr**3
        )
        return P_copper + P_stray  # W, shape (n,)

    @override
    def update_dynamic(
        self,
        params: dict[str, PlainQuantity[float]],
        velocities_si: np.ndarray,
        sub_dt: float,
    ) -> PlainQuantity[float]:
        v = velocities_si  # m/s, shape (n,)

        wheel_circumference = np.pi * params["wheel_diameter"].to("m").magnitude
        N_rpm_arr = v / wheel_circumference * 60.0  # rpm, shape (n,)

        # Road load power vectors from RR and drag (set earlier in update_dynamic loop)
        rr_vec: np.ndarray = params.get(
            "_rr_power_vec", np.full_like(v, abs(params["rr_power"].to("W").magnitude))
        )  # type: ignore[assignment]
        drag_vec: np.ndarray = params.get(
            "_drag_power_vec",
            np.full_like(v, abs(params["drag_power"].to("W").magnitude)),
        )  # type: ignore[assignment]

        battery_voltage = params["battery_voltage_nominal"].to("V").magnitude
        I_arr = (rr_vec + drag_vec) / battery_voltage  # A, shape (n,)

        loss_vec = self._loss_vec(I_arr, N_rpm_arr, params)  # W, shape (n,)

        # Store time-averaged scalars for logging
        params["motor_current"] = Q_(float(np.mean(I_arr)), "A")
        params["motor_speed"] = Q_(float(np.mean(N_rpm_arr)), "rpm")
        params["motor_P_total"] = Q_(float(np.mean(loss_vec)), "W")

        energy_J = float(np.trapezoid(loss_vec, dx=sub_dt))
        return Q_(-energy_J / 3600.0, "Wh")
