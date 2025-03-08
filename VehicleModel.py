from pint import UnitRegistry
import math
import matplotlib.pyplot as plt

UR = UnitRegistry()

class VehicleModel:
    def __init__(self, inputs_dict):
        # Iterate through inputs_dict and set each key as an attribute
        for key, value in inputs_dict.items():
            setattr(self, key, value)

    def pwr_loss(self):
        self.weight = self.base_weight + self.aero_weight
        self.drag_loss = (self.drag_coeff * self.drag_area * 0.5 * self.air_density * (self.avg_velocity**3)).to('watts')

        self.frictional_loss = ((self.weight * (self.mu + (self.mu2*(self.avg_velocity)))) * self.avg_velocity).to('watts')

        self.loss = (self.drag_loss + self.frictional_loss)

        return self.loss

    def pwr_gen(self):
        self.back_gen = (self.back_subarray_ct * self.v_mpp * self.i_mpp * math.cos(math.radians(self.back_incident_angle))).to('watts')

        self.lr_gen = (self.lr_subarray_ct * self.v_mpp * self.i_mpp * math.cos(math.radians(self.lr_incident_angle))).to('watts') * 2

        self.gen = (self.back_gen + self.lr_gen)

        return self.gen
    
    def print_vars(self):
        for key, value in vars(self).items():
            print(f"{key}: {value}")
    
    def run(self):
        self.print_vars()

        power_loss = self.pwr_loss()

        power_gen = self.pwr_gen()

        return power_gen, power_loss

# Inputs
inputs_dict = {
    # General
    "avg_velocity": 9 * UR.mps, # m/s | average velocity

    # Drag
    "drag_coeff": 0.1305, # drag coefficient
    "drag_area": 0.9117 * (UR.meter**2), # m^2
    "air_density": 1.225 * UR.kilogram/(UR.meter**3), # kg/m^3

    # Array
    "mppt_eff": 0.985,
    "v_mpp": 0.45 * UR.volts, # obtained from tests
    "i_mpp": 2.96 * UR.amperes, # obtained from tests

    "back_subarray_ct": 128,
    "lr_subarray_ct": 120,
    "back_incident_angle": 0 * UR.degrees, # degrees
    "lr_incident_angle": 0 * UR.degrees, # degrees

    "del_t": 20 * UR.miles / (9 * UR.mps), # hrs | time spent racing

    # Aeroshell
    "aero_weight": 90.6 * UR.force_pound, # lbs
    "base_weight": 500 * UR.force_pound, # lbs

    # Rolling Resistance
    "mu": 0.00175, # dimensionless | rolling resistance coefficient
    "mu2": 0.0000311 * (UR.hour/UR.kilometer), # rolling resistance coefficient wrt velocity

    "battery_eff": 0.95,
    "frac_soc": 1, # % | fractional state of charge
    "battery_E_max": 5240 * UR.kilowatt_hour, # | fully charged energy of battery
}

# # Functions
# def get_grad(setter):



# # vary speed until power gen == power loss
# def get_optimal():
#     # gradient descent
    

model = VehicleModel(inputs_dict)
model.run()