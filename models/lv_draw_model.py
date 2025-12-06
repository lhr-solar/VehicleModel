from typing import override
from pint import Quantity 

class LVDrawModel():
     def __init__(self):
        super().__init__()
        self.components = [
         'vcu', 'controls_leader', 'horn', 'lighting', 'pi_&_display', 
         'pedals', 'camera_hub', 'battery_box', 'mppt_a', 'mppta_b', 
         'mppt_c', 'motor_controller', 'telemetry_leader', 'pump'
     ] 
     @override
     def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]: 
        mode = params.get('lv_mode', 'constant')
        suffix = "_peak" if mode == 'peak' else "_const"
        for component in self.componenets:
            peak_key = f"{component}{suffix}"
            constant_key = component
            if peak_key in params:
                total_current += params[peak_key]
            elif constant_key in params:
                total_current += params[constant_key]
            else:
               pass
        params['lv_draw_power'] = 24*total_current
        return params['lv_draw_power'] * timestep