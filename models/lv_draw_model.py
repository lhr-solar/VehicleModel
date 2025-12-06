# from typing import override
# from pint import Quantity 

# class LVDrawModel():
#     def __init__(self):
#         super().__init__()
#     self.components = [
#         'vcu', 'controls_leader', 'horn', 'lighting', 'pi_&_display', 
#         'pedals', 'camera_hub', 'battery_box', 'mppt_a', 'mppta_b', 
#         'mppt_c', 'motor_controller', 'telemetry_leader', 'pump'
#     ] 
#     @override
#     def update(self, params: dict[str, Quantity[float]], timestep: Quantity[float]) -> Quantity[float]: 
#         params['lv_draw_power'] = 24 * (params['vcu']+params['controls_leader']
#                                         +params['horn']+params['lighting']
#                                         +params['pi_&_display']+params['pedals']
#                                         +params['camera_hub']+params['battery_box']
#                                         +params['mppt_a']+params['mppt_b']
#                                         +params['mppt_c']+params['motor_controller']
#                                         +params['telemetry_leader']+params['pump'])
#         return params['lv_draw_power']