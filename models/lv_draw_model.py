from typing import override
from pint import Quantity
from .energy_model import EnergyModel

class LVDrawModel(EnergyModel):
     def __init__(self):
        super().__init__()
        self.components = [
         'vcu', 'controls_leader', 'horn', 'lighting', 'pi_&_display', 
         'pedals', 'camera_hub', 'battery_box', 'mppt_a', 'mppt_b', 
         'mppt_c', 'motor_controller', 'telemetry_leader', 'pump', 'DC_DC_converter'
        ] 
     @override
     def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]: 
        mode = params.get('enable_peak_draw', 0)
        suffix = "_peak" if mode == 1 else ""
        total_current = sum(params.get(f"{component}{suffix}", params.get(component, 0)) for component in self.components)
        params['lv_draw_power'] = params['lv_voltage'] * total_current

        return -params['lv_draw_power'] * timestep