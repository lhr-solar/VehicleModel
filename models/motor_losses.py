import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Dict


@dataclass
class MotorParameters:
    k_T: float
    k_C: float
    k_S: float
    R_A: float
    R_B: float
    k_H: float = 0.0
    k_E: float = 0.0
    k_B1: float = 0.0
    k_B2: float = 0.0
    k_D: float = 0.0
    k_SW: float = 0.0
    k_1: float = 0.0
    k_2: float = 0.0
    k_3: float = 0.0
    is_brushless: bool = False
    eta_C: float = 0.97
    T_ref: float = 25.0
    T_operating: float = 70.0
    
    @property
    def R_total(self) -> float:
        alpha = 0.00393
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


def create_example_motor_BRLS8() -> MotorParameters:
    k_0 = 4.0578
    k_01 = -3.4388e-4
    k_02 = 1.8342e-8
    k_1 = 0.01114
    k_2 = 2.1575e-6
    k_3 = 0.0
    
    k_C = 0.020
    k_S = k_C * 9.549
    k_T = k_S
    
    R_over_kS2 = k_0 + k_01*3000 + k_02*3000**2
    R_total = R_over_kS2 * k_S**2
    R_A = 0.8 * R_total
    R_B = 0.2 * R_total
    
    return MotorParameters(
        k_T=k_T,
        k_C=k_C,
        k_S=k_S,
        R_A=R_A,
        R_B=R_B,
        k_1=k_1,
        k_2=k_2,
        k_3=k_3,
        is_brushless=True,
        eta_C=0.97
    )


def create_example_motor_HSSS3810() -> MotorParameters:
    return MotorParameters(
        k_T=0.2152,
        k_C=0.02254,
        k_S=0.2152,
        R_A=0.048,
        R_B=0.012,
        is_brushless=False,
        eta_C=1.0
    )


if __name__ == "__main__":
    motor_params = create_example_motor_BRLS8()
    model = MotorLossModel(motor_params)
    
    print("\nEXAMPLE 1: CRUISING")
    model.print_loss_analysis(tau_S=5.0, N_rpm=3800, V_bus=84.0, 
                             use_stray_model=True)
    
    print("\n\nEXAMPLE 2: HILL CLIMBING")
    model.print_loss_analysis(tau_S=10.0, N_rpm=2000, V_bus=84.0,
                             use_stray_model=True)
    
    print("\n\nEXAMPLE 3: OPTIMAL TORQUE AT 3000 RPM")
    tau_opt = model.optimal_torque(N_rpm=3000)
    print(f"\nOptimal torque: {tau_opt:.2f} N·m")
    model.print_loss_analysis(tau_S=tau_opt, N_rpm=3000, V_bus=84.0,
                             use_stray_model=True)