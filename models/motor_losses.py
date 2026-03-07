import numpy as np
from typing import Dict, override
from pint.facets.plain import PlainQuantity
from models.energy_model import EnergyModel
from units import Q_


class MotorLossModel(EnergyModel):
    def __init__(self):
        super().__init__()

    def total_motor_loss(
        self,
        I: PlainQuantity[float],
        N_rpm: PlainQuantity[float],
        params: dict[str, PlainQuantity[float]],
    ) -> Dict[str, PlainQuantity[float]]:
        # Extract parameters
        R_A = params["motor_R_A"]
        R_B = params["motor_R_B"]
        k_H = params["motor_k_H_default"]
        k_E = params["motor_k_E_default"]
        k_B1 = params["motor_k_B1_default"]
        k_B2 = params["motor_k_B2_default"]
        k_D = params["motor_k_D_default"]

        # Current-dependent losses
        P_armature = I**2 * R_A
        P_commutation = I**2 * R_B
        P_copper_total = P_armature + P_commutation

        # Speed-dependent losses (physics-based individual models)
        P_hysteresis = k_H * N_rpm
        P_eddy = k_E * N_rpm**2
        P_bearing = (k_B1 + k_B2 * N_rpm) * N_rpm
        P_air_drag = k_D * N_rpm**3
        P_stray = P_hysteresis + P_eddy + P_bearing + P_air_drag

        P_total = P_copper_total + P_stray  # type: ignore

        return {
            "P_armature": P_armature,
            "P_commutation": P_commutation,
            "P_copper_total": P_copper_total,
            "P_hysteresis": P_hysteresis,
            "P_eddy": P_eddy,
            "P_bearing": P_bearing,
            "P_air_drag": P_air_drag,
            "P_stray_total": P_stray,
            "P_motor_total": P_total,
        }

    def motor_efficiency(
        self,
        tau_S: PlainQuantity[float],
        N_rpm: PlainQuantity[float],
        params: dict[str, PlainQuantity[float]],
    ) -> Dict[str, PlainQuantity[float]]:
        k_S = params["motor_k_S"]
        eta_C = params["motor_eta_C"]
        I = tau_S / k_S
        # Convert torque × rpm to power in Watts
        P_shaft = (tau_S * N_rpm).to("W")
        losses = self.total_motor_loss(I, N_rpm, params)
        P_motor_input = P_shaft + losses["P_motor_total"]
        eta_motor = (
            P_shaft / P_motor_input
            if P_motor_input > Q_(0, "W")
            else Q_(0, "dimensionless")
        )

        P_controller_loss = P_motor_input * (1 / eta_C - 1)
        P_battery_input = P_motor_input / eta_C
        eta_system = P_shaft / P_battery_input

        return {
            "I": I,
            "N_rpm": N_rpm,
            "tau_S": tau_S,
            "P_shaft": P_shaft,
            "P_motor_input": P_motor_input,
            "P_battery_input": P_battery_input,
            "eta_motor": eta_motor,
            "eta_system": eta_system,
            "P_controller_loss": P_controller_loss,
            **losses,
        }

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        # Calculate motor speed from velocity and wheel circumference
        velocity = params["velocity"]
        wheel_diameter = params["wheel_diameter"]
        wheel_circumference = np.pi * wheel_diameter
        # Convert velocity to rotational speed
        N_rpm = (velocity / wheel_circumference).to("rpm")

        # Calculate motor current from power demands
        drag_power = params["drag_power"]
        rr_power = params["rr_power"]
        battery_voltage = params["battery_voltage_nominal"]
        I = (drag_power + rr_power) / battery_voltage

        # Calculate all motor losses
        losses = self.total_motor_loss(I, N_rpm, params)

        # Store calculated values for logging
        params["motor_current"] = I
        params["motor_speed"] = N_rpm

        # Store individual losses in params for logging (standardized to watts)
        params["motor_P_armature"] = losses["P_armature"].to("W")
        params["motor_P_commutation"] = losses["P_commutation"].to("W")
        params["motor_P_copper_total"] = losses["P_copper_total"].to("W")
        params["motor_P_hysteresis"] = losses["P_hysteresis"].to("W")
        params["motor_P_eddy"] = losses["P_eddy"].to("W")
        params["motor_P_bearing"] = losses["P_bearing"].to("W")
        params["motor_P_air_drag"] = losses["P_air_drag"].to("W")
        params["motor_P_stray_total"] = losses["P_stray_total"].to("W")
        params["motor_P_total"] = losses["P_motor_total"].to("W")

        # Return energy lost in this timestep (negative because it's a loss)
        return -losses["P_motor_total"] * timestep
