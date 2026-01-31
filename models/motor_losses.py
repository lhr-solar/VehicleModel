import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, override
from pathlib import Path
from pint.facets.plain import PlainQuantity
from models.energy_model import EnergyModel
from units import Q_


class MotorLossModel(EnergyModel):
    
    def __init__(self):
        super().__init__()
    
    def R_total(self, params: dict[str, PlainQuantity[float]]) -> PlainQuantity[float]:
        alpha = params['copper_temp_coefficient_alpha']
        T_ref = params['motor_T_ref_default']
        T_operating = params['motor_T_operating_default']
        R_A = params['motor_R_A']
        R_B = params['motor_R_B']
        dT = T_operating - T_ref
        R_hot = (R_A + R_B) * (1 + alpha * dT)
        return R_hot
    
    def R_equivalent_battery_side(self, params: dict[str, PlainQuantity[float]]) -> PlainQuantity[float]:
        eta_C = params['motor_eta_C']
        return 1.5 * self.R_total(params) / eta_C
    
    def total_motor_loss(self, I: PlainQuantity[float], N_rpm: PlainQuantity[float], params: dict[str, PlainQuantity[float]]) -> Dict[str, PlainQuantity[float]]:
        # Extract parameters
        R_A = params['motor_R_A']
        R_B = params['motor_R_B']
        k_SW = params['motor_k_SW_default']
        k_H = params['motor_k_H_default']
        k_E = params['motor_k_E_default']
        k_B1 = params['motor_k_B1_default']
        k_B2 = params['motor_k_B2_default']
        k_D = params['motor_k_D_default']
        
        # Current-dependent losses
        P_armature = I**2 * R_A
        P_commutation = k_SW * N_rpm + I**2 * R_B
        P_copper_total = P_armature + P_commutation
        
        # Speed-dependent losses (physics-based individual models)
        P_hysteresis = k_H * N_rpm
        P_eddy = k_E * N_rpm**2
        P_bearing = (k_B1 + k_B2 * N_rpm) * N_rpm
        P_air_drag = k_D * N_rpm**3
        P_stray = P_hysteresis + P_eddy + P_bearing + P_air_drag
        
        P_total = P_copper_total + P_stray # type: ignore
        
        return {
            'P_armature': P_armature,
            'P_commutation': P_commutation,
            'P_copper_total': P_copper_total,
            'P_hysteresis': P_hysteresis,
            'P_eddy': P_eddy,
            'P_bearing': P_bearing,
            'P_air_drag': P_air_drag,
            'P_stray_total': P_stray,
            'P_motor_total': P_total
        }
    
    def motor_efficiency(self, tau_S: PlainQuantity[float], N_rpm: PlainQuantity[float], params: dict[str, PlainQuantity[float]]) -> Dict[str, PlainQuantity[float]]:
        k_S = params['motor_k_S']
        eta_C = params['motor_eta_C']
        I = tau_S / k_S
        # Convert (N·m × rpm) to Watts: 9.549 = 60/(2π) for rpm to rad/s conversion
        P_shaft = tau_S * N_rpm / Q_(9.549, 'dimensionless')
        losses = self.total_motor_loss(I, N_rpm, params)
        P_motor_input = P_shaft + losses['P_motor_total']
        eta_motor = P_shaft / P_motor_input if P_motor_input > Q_(0, 'W') else Q_(0, 'dimensionless')
        
        # Motor is brushless
        P_controller_loss = P_motor_input * (1/eta_C - 1)
        P_battery_input = P_motor_input / eta_C
        eta_system = P_shaft / P_battery_input
        
        return {
            'I': I,
            'N_rpm': N_rpm,
            'tau_S': tau_S,
            'P_shaft': P_shaft,
            'P_motor_input': P_motor_input,
            'P_battery_input': P_battery_input,
            'eta_motor': eta_motor,
            'eta_system': eta_system,
            'P_controller_loss': P_controller_loss,
            **losses
        }
    
    def optimal_torque(self, N_rpm: PlainQuantity[float], params: dict[str, PlainQuantity[float]]) -> PlainQuantity[float]:
        # Calculate stray losses using physics-based models
        k_H = params['motor_k_H_default']
        k_E = params['motor_k_E_default']
        k_B1 = params['motor_k_B1_default']
        k_B2 = params['motor_k_B2_default']
        k_D = params['motor_k_D_default']
        P_L = k_H * N_rpm + k_E * N_rpm**2 + (k_B1 + k_B2 * N_rpm) * N_rpm + k_D * N_rpm**3
        R = self.R_total(params)
        k_S = params['motor_k_S']
        tau_optimal = np.sqrt(P_L * k_S**2 / R)
        return tau_optimal
    
    def controller_loss(self, P_motor: PlainQuantity[float], params: dict[str, PlainQuantity[float]]) -> Dict[str, PlainQuantity[float]]:
        eta_C = params['motor_eta_C']
        P_controller_loss = P_motor * (1/eta_C - 1)
        P_battery = P_motor + P_controller_loss
        
        return {
            'P_motor': P_motor,
            'P_controller_loss': P_controller_loss,
            'P_battery': P_battery,
            'eta_controller': eta_C
        }
    
    def system_power_analysis(self, tau_S: PlainQuantity[float], N_rpm: PlainQuantity[float], V_bus: PlainQuantity[float], params: dict[str, PlainQuantity[float]]) -> Dict[str, PlainQuantity[float]]:
        motor_results = self.motor_efficiency(tau_S, N_rpm, params)
        I = motor_results['I']
        k_C = params['motor_k_C']
        V_emf = k_C * N_rpm
        V_resistive = I * self.R_total(params)
        
        return {
            **motor_results,
            'V_bus': V_bus,
            'V_emf': V_emf,
            'V_resistive': V_resistive,
            'V_required': V_emf + V_resistive
        }
    
    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        # Calculate motor speed from velocity and wheel circumference
        # N_rpm = (velocity / wheel_circumference) * 60
        import numpy as np
        velocity = params.get('velocity', Q_(0, 'm/s'))
        wheel_diameter = params.get('wheel_diameter', Q_(0.5, 'm'))  
        wheel_circumference = np.pi * wheel_diameter
        # Convert velocity to rotational speed
        N_rpm = (velocity / wheel_circumference * Q_(60, 's/min')).to('rpm')
        
        # Calculate motor current from power demands
        # I = (drag_power + rr_power) / battery_voltage
        drag_power = params.get('drag_power', Q_(0, 'W'))
        rr_power = params.get('rr_power', Q_(0, 'W'))
        battery_voltage = params.get('battery_voltage_nominal', Q_(115.2, 'V'))
        I = (drag_power + rr_power) / battery_voltage
        
        # Calculate all motor losses
        losses = self.total_motor_loss(I, N_rpm, params)
        
        # Store calculated values for logging
        params['motor_current'] = I
        params['motor_speed'] = N_rpm
        
        # Store individual losses in params for logging
        params['motor_P_armature'] = losses['P_armature']
        params['motor_P_commutation'] = losses['P_commutation']
        params['motor_P_copper_total'] = losses['P_copper_total']
        params['motor_P_hysteresis'] = losses['P_hysteresis']
        params['motor_P_eddy'] = losses['P_eddy']
        params['motor_P_bearing'] = losses['P_bearing']
        params['motor_P_air_drag'] = losses['P_air_drag']
        params['motor_P_stray_total'] = losses['P_stray_total']
        params['motor_P_total'] = losses['P_motor_total']
        
        # Return energy lost in this timestep (negative because it's a loss)
        return -losses['P_motor_total'] * timestep

