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
    
    def R_total(self, params: dict[str, PlainQuantity[float]]) -> float:
        alpha = params['copper_temp_coefficient_alpha'].magnitude
        T_ref = params['motor_T_ref_default'].magnitude
        T_operating = params['motor_T_operating_default'].magnitude
        R_A = params['motor_R_A'].magnitude
        R_B = params['motor_R_B'].magnitude
        dT = T_operating - T_ref
        R_hot = (R_A + R_B) * (1 + alpha * dT)
        return R_hot
    
    def R_equivalent_battery_side(self, params: dict[str, PlainQuantity[float]]) -> float:
        eta_C = params['motor_eta_C'].magnitude
        return 1.5 * self.R_total(params) / eta_C
    
    def total_motor_loss(self, I: float, N_rpm: float, params: dict[str, PlainQuantity[float]]) -> Dict[str, float]:
        # Extract parameters
        R_A = params['motor_R_A'].magnitude
        R_B = params['motor_R_B'].magnitude
        k_SW = params['motor_k_SW_default'].magnitude
        k_H = params['motor_k_H_default'].magnitude
        k_E = params['motor_k_E_default'].magnitude
        k_B1 = params['motor_k_B1_default'].magnitude
        k_B2 = params['motor_k_B2_default'].magnitude
        k_D = params['motor_k_D_default'].magnitude
        
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
        
        P_total = P_copper_total + P_stray
        
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
    
    def motor_efficiency(self, tau_S: float, N_rpm: float, params: dict[str, PlainQuantity[float]]) -> Dict[str, float]:
        k_S = params['motor_k_S'].magnitude
        eta_C = params['motor_eta_C'].magnitude
        I = tau_S / k_S
        P_shaft = tau_S * N_rpm / 9.549
        losses = self.total_motor_loss(I, N_rpm, params)
        P_motor_input = P_shaft + losses['P_motor_total']
        eta_motor = P_shaft / P_motor_input if P_motor_input > 0 else 0
        
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
    
    def optimal_torque(self, N_rpm: float, params: dict[str, PlainQuantity[float]]) -> float:
        # Calculate stray losses using physics-based models
        k_H = params['motor_k_H_default'].magnitude
        k_E = params['motor_k_E_default'].magnitude
        k_B1 = params['motor_k_B1_default'].magnitude
        k_B2 = params['motor_k_B2_default'].magnitude
        k_D = params['motor_k_D_default'].magnitude
        P_L = k_H * N_rpm + k_E * N_rpm**2 + (k_B1 + k_B2 * N_rpm) * N_rpm + k_D * N_rpm**3
        R = self.R_total(params)
        k_S = params['motor_k_S'].magnitude
        tau_optimal = np.sqrt(P_L * k_S**2 / R)
        return tau_optimal
    
    def controller_loss(self, P_motor: float, params: dict[str, PlainQuantity[float]]) -> Dict[str, float]:
        eta_C = params['motor_eta_C'].magnitude
        P_controller_loss = P_motor * (1/eta_C - 1)
        P_battery = P_motor + P_controller_loss
        
        return {
            'P_motor': P_motor,
            'P_controller_loss': P_controller_loss,
            'P_battery': P_battery,
            'eta_controller': eta_C
        }
    
    def system_power_analysis(self, tau_S: float, N_rpm: float, V_bus: float, params: dict[str, PlainQuantity[float]]) -> Dict[str, float]:
        motor_results = self.motor_efficiency(tau_S, N_rpm, params)
        I = motor_results['I']
        k_C = params['motor_k_C'].magnitude
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
        # Placeholder - motor losses can be analyzed using the other methods
        # but are not automatically calculated during simulation
        return Q_(0, "joule")
    
    def print_loss_analysis(self, tau_S: float, N_rpm: float, V_bus: float, params: dict[str, PlainQuantity[float]]):
        results = self.system_power_analysis(tau_S, N_rpm, V_bus, params)
        eta_C = params['motor_eta_C'].magnitude
        
        print("="*70)
        print(f"MOTOR LOSS ANALYSIS: {N_rpm:.0f} RPM, {tau_S:.2f} N·m")
        print("="*70)
        
        print(f"\nELECTRICAL:")
        print(f"  Current:             {results['I']:.2f} A")
        print(f"  Back-EMF:            {results['V_emf']:.2f} V")
        print(f"  Resistive drop:      {results['V_resistive']:.2f} V")
        print(f"  Required voltage:    {results['V_required']:.2f} V")
        
        print(f"\nCURRENT-DEPENDENT LOSSES:")
        print(f"  Armature (I²R_A):    {results['P_armature']:.1f} W")
        print(f"  Commutation (I²R_B): {results['P_commutation']:.1f} W")
        print(f"  Total copper:        {results['P_copper_total']:.1f} W")
        
        print(f"\nSPEED-DEPENDENT LOSSES:")
        print(f"  Hysteresis:          {results['P_hysteresis']:.1f} W")
        print(f"  Eddy current:        {results['P_eddy']:.1f} W")
        print(f"  Bearing friction:    {results['P_bearing']:.1f} W")
        print(f"  Air drag:            {results['P_air_drag']:.1f} W")
        print(f"  Total stray:         {results['P_stray_total']:.1f} W")
        
        print(f"\nPOWER SUMMARY:")
        print(f"  Shaft output:        {results['P_shaft']:.1f} W")
        print(f"  Motor losses:        {results['P_motor_total']:.1f} W")
        print(f"  Motor input:         {results['P_motor_input']:.1f} W")
        print(f"  Controller loss:     {results['P_controller_loss']:.1f} W")
        print(f"  Battery input:       {results['P_battery_input']:.1f} W")
        
        print(f"\nEFFICIENCY:")
        print(f"  Motor:               {results['eta_motor']*100:.2f}%")
        print(f"  Controller:          {eta_C*100:.2f}%")
        print(f"  System:              {results['eta_system']*100:.2f}%")
        print("="*70)
