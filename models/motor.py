from models.base import ModelPlugin
from pint import Quantity
import numpy as np

class MotorLossModel(ModelPlugin):
    def __init__(self, efficiency: float):
        super().__init__()
        self.efficiency = efficiency  # Efficiency as a decimal (e.g., 0.9 for 90%)

    def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]:
        # Calculate motor losses based on power output and efficiency
        motor_current = params["motor_current"].to("A").magnitude
        motor_rpm = params["motor_rpm"].to("rpm").magnitude
        motor_temperature = params.get("motor_temperature", 25.0)  # Default 25°C
        
        if isinstance(motor_temperature, Quantity):
            motor_temperature = motor_temperature.to("degC").magnitude

        temp_ref = 25.0  # Reference temperature (°C)
        temp_coefficient = 0.00393  # 1/°C for copper
        temp_factor = 1 + temp_coefficient * (motor_temperature - temp_ref)

        R_A_25C = params.get("armature_resistance_25C", 0.025)  # Ω at 25°C
        if isinstance(R_A_25C, Quantity):
            R_A_25C = R_A_25C.to("ohm").magnitude
        