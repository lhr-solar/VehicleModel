import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Dict
from pathlib import Path
import yaml


# Load parameters from params.yaml
def load_params():
    params_file = Path(__file__).parent.parent / "params.yaml"
    with open(params_file, 'r') as f:
        params_list = yaml.safe_load(f)
    params_dict = {p['name']: p['value'] for p in params_list}
    return params_dict

PARAMS = load_params()


@dataclass
class MotorParameters:
    k_T: float
    k_C: float
    k_S: float
    R_A: float
    R_B: float
    k_H: float = PARAMS['motor_k_H_default']
    k_E: float = PARAMS['motor_k_E_default']
    k_B1: float = PARAMS['motor_k_B1_default']
    k_B2: float = PARAMS['motor_k_B2_default']
    k_D: float = PARAMS['motor_k_D_default']
    k_SW: float = PARAMS['motor_k_SW_default']
    k_1: float = PARAMS['motor_k_1_default']
    k_2: float = PARAMS['motor_k_2_default']
    k_3: float = PARAMS['motor_k_3_default']
    is_brushless: bool = PARAMS['motor_is_brushless_default']
    eta_C: float = PARAMS['motor_eta_C_default']
    T_ref: float = PARAMS['motor_T_ref_default']
    T_operating: float = PARAMS['motor_T_operating_default']
    
    @property
    def R_total(self) -> float:
        alpha = PARAMS['copper_temp_coefficient_alpha']
        dT = self.T_operating - self.T_ref
        R_hot = (self.R_A + self.R_B) * (1 + alpha * dT)
        return R_hot
    
    @property
    def R_equivalent_battery_side(self) -> float:
        if self.is_brushless:
            return 1.5 * self.R_total / self.eta_C
        else:
            return self.R_total


class MotorLossModel:
    
    def __init__(self, params: MotorParameters):
        self.params = params
    
    def armature_loss(self, I: float) -> float:
        return I**2 * self.params.R_A
    
    def commutation_loss(self, I: float, N_rpm: float) -> float:
        if self.params.is_brushless:
            P_switching = self.params.k_SW * N_rpm
            P_conduction = I**2 * self.params.R_B
            return P_switching + P_conduction
        else:
            return I**2 * self.params.R_B
    
    def hysteresis_loss(self, N_rpm: float) -> float:
        return self.params.k_H * N_rpm
    
    def eddy_current_loss(self, N_rpm: float) -> float:
        return self.params.k_E * N_rpm**2
    
    def bearing_loss(self, N_rpm: float) -> float:
        torque_friction = self.params.k_B1 + self.params.k_B2 * N_rpm
        P_bearing = torque_friction * N_rpm
        return P_bearing
    
    def air_drag_loss(self, N_rpm: float) -> float:
        return self.params.k_D * N_rpm**3
    
    def stray_power_loss(self, N_rpm: float) -> float:
        return (self.params.k_1 * N_rpm + 
                self.params.k_2 * N_rpm**2 + 
                self.params.k_3 * N_rpm**3)
    
    def total_motor_loss(self, I: float, N_rpm: float, 
                        use_stray_model: bool = False) -> Dict[str, float]:
        P_armature = self.armature_loss(I)
        P_commutation = self.commutation_loss(I, N_rpm)
        P_copper_total = P_armature + P_commutation
        
        if use_stray_model and (self.params.k_1 != 0 or 
                               self.params.k_2 != 0 or 
                               self.params.k_3 != 0):
            P_stray = self.stray_power_loss(N_rpm)
            P_hysteresis = 0
            P_eddy = 0
            P_bearing = 0
            P_air_drag = 0
        else:
            P_hysteresis = self.hysteresis_loss(N_rpm)
            P_eddy = self.eddy_current_loss(N_rpm)
            P_bearing = self.bearing_loss(N_rpm)
            P_air_drag = self.air_drag_loss(N_rpm)
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
    
    def motor_efficiency(self, tau_S: float, N_rpm: float,
                        use_stray_model: bool = False) -> Dict[str, float]:
        I = tau_S / self.params.k_S
        P_shaft = tau_S * N_rpm / 9.549
        losses = self.total_motor_loss(I, N_rpm, use_stray_model)
        P_motor_input = P_shaft + losses['P_motor_total']
        eta_motor = P_shaft / P_motor_input if P_motor_input > 0 else 0
        
        if self.params.is_brushless:
            P_controller_loss = P_motor_input * (1/self.params.eta_C - 1)
            P_battery_input = P_motor_input / self.params.eta_C
            eta_system = P_shaft / P_battery_input
        else:
            P_controller_loss = 0
            P_battery_input = P_motor_input
            eta_system = eta_motor
        
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
    
    def optimal_torque(self, N_rpm: float) -> float:
        P_L = self.stray_power_loss(N_rpm)
        R = self.params.R_total
        k_S = self.params.k_S
        tau_optimal = np.sqrt(P_L * k_S**2 / R)
        return tau_optimal
    
    def controller_loss(self, P_motor: float) -> Dict[str, float]:
        if not self.params.is_brushless:
            return {
                'P_motor': P_motor,
                'P_controller_loss': 0,
                'P_battery': P_motor,
                'eta_controller': 1.0
            }
        
        P_controller_loss = P_motor * (1/self.params.eta_C - 1)
        P_battery = P_motor + P_controller_loss
        
        return {
            'P_motor': P_motor,
            'P_controller_loss': P_controller_loss,
            'P_battery': P_battery,
            'eta_controller': self.params.eta_C
        }
    
    def system_power_analysis(self, tau_S: float, N_rpm: float, V_bus: float,
                             use_stray_model: bool = False) -> Dict[str, float]:
        motor_results = self.motor_efficiency(tau_S, N_rpm, use_stray_model)
        I = motor_results['I']
        V_emf = self.params.k_C * N_rpm
        V_resistive = I * self.params.R_total
        
        return {
            **motor_results,
            'V_bus': V_bus,
            'V_emf': V_emf,
            'V_resistive': V_resistive,
            'V_required': V_emf + V_resistive
        }
    
    def print_loss_analysis(self, tau_S: float, N_rpm: float, V_bus: float,
                          use_stray_model: bool = False):
        results = self.system_power_analysis(tau_S, N_rpm, V_bus, use_stray_model)
        
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
        if use_stray_model:
            print(f"  Stray (combined):    {results['P_stray_total']:.1f} W")
        else:
            print(f"  Hysteresis:          {results['P_hysteresis']:.1f} W")
            print(f"  Eddy current:        {results['P_eddy']:.1f} W")
            print(f"  Bearing friction:    {results['P_bearing']:.1f} W")
            print(f"  Air drag:            {results['P_air_drag']:.1f} W")
            print(f"  Total stray:         {results['P_stray_total']:.1f} W")
        
        print(f"\nPOWER SUMMARY:")
        print(f"  Shaft output:        {results['P_shaft']:.1f} W")
        print(f"  Motor losses:        {results['P_motor_total']:.1f} W")
        print(f"  Motor input:         {results['P_motor_input']:.1f} W")
        
        if self.params.is_brushless:
            print(f"  Controller loss:     {results['P_controller_loss']:.1f} W")
            print(f"  Battery input:       {results['P_battery_input']:.1f} W")
        
        print(f"\nEFFICIENCY:")
        print(f"  Motor:               {results['eta_motor']*100:.2f}%")
        if self.params.is_brushless:
            print(f"  Controller:          {self.params.eta_C*100:.2f}%")
        print(f"  System:              {results['eta_system']*100:.2f}%")
        print("="*70)


def load_motor_from_params() -> MotorParameters:
    """Load motor parameters from params.yaml"""
    return MotorParameters(
        k_T=PARAMS['motor_k_T'],
        k_C=PARAMS['motor_k_C'],
        k_S=PARAMS['motor_k_S'],
        R_A=PARAMS['motor_R_A'],
        R_B=PARAMS['motor_R_B'],
        is_brushless=PARAMS['motor_is_brushless'],
        eta_C=PARAMS['motor_eta_C']
    )


if __name__ == "__main__":
    # Load motor from params.yaml
    motor = load_motor_from_params()
    model = MotorLossModel(motor)
    
    # Print motor configuration
    print("\n" + "="*70)
    print("MOTOR CONFIGURATION FROM params.yaml")
    print("="*70)
    print(f"Motor Type:          {'Brushless' if motor.is_brushless else 'Brushed'}")
    print(f"Torque Constant:     {motor.k_T:.4f} N·m/A")
    print(f"Voltage Constant:    {motor.k_C:.4f} V·min/rad")
    print(f"Speed Constant:      {motor.k_S:.4f} N·m/A")
    print(f"Armature Resistance: {motor.R_A:.4f} Ω")
    print(f"Field Resistance:    {motor.R_B:.4f} Ω")
    print(f"Controller Eff.:     {motor.eta_C*100:.1f}%")
    print(f"Operating Temp:      {motor.T_operating:.1f}°C")
    print("="*70 + "\n")
