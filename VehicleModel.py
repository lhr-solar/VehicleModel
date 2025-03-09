from pint import UnitRegistry
import math
import matplotlib.pyplot as plt
import numpy as np

import time

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

        self.power_loss = (self.drag_loss + self.frictional_loss)

        return self.power_loss

    def pwr_gen(self):
        self.back_gen = (self.back_subarray_ct * self.v_mpp * self.i_mpp * math.cos(math.radians(self.back_incident_angle))).to('watts')

        self.lr_gen = (self.lr_subarray_ct * self.v_mpp * self.i_mpp * math.cos(math.radians(self.lr_incident_angle))).to('watts') * 2

        self.power_gen = (self.back_gen + self.lr_gen)

        return self.power_gen
    
    def print_vars(self):
        for key, value in vars(self).items():
            print(f"{key}: {value}")
    
    def run(self):
        power_loss = self.pwr_loss()

        power_gen = self.pwr_gen()

        return power_gen, power_loss
    
    def get_grad(self, key_x, loss_function, step=0.0001):
        curr_key_x = getattr(self, key_x)
        self.run()
        curr_out = loss_function(self)

        new_key_x = curr_key_x + (step * curr_key_x.units)
        setattr(self, key_x, new_key_x)
        self.run()
        new_out = loss_function(self)

        grad = (new_out - curr_out) / step

        # Reset key
        setattr(self, key_x, curr_key_x)

        return grad
    
    def get_optimal_gd(self, 
                    key_x, 
                    loss_function, 
                    lr, 
                    tolerance=0.0001):
        initial_val = getattr(self, key_x)

        points = []
        
        print("=====================================")

        # gradient descent
        while True:
            grad = self.get_grad(key_x, loss_function)
            print(f"Gradient: {grad}")

            update = lr * grad
            print(f"Update: {update}")
            
            updated_x = getattr(self, key_x) - (update * initial_val.units)
            updated_x = updated_x.to(initial_val.units)
            setattr(self, key_x, updated_x)
            print(f"New {key_x}: {getattr(self, key_x)}")

            loss = loss_function(self)
            print(f"Loss: {loss}")
            if abs(loss) < tolerance:
                break

            points.append((getattr(self, key_x).m, loss))

            print("=====================================")

        final_val = getattr(self, key_x)

        # maintain the initial value
        setattr(self, key_x, initial_val)

        # Plotting
        x = [point[0] for point in points]
        y = [point[1] for point in points]

        plt.plot(x, y)
        plt.xlabel(key_x)
        plt.ylabel("Loss")
        plt.title(f"{key_x} vs Loss")
        plt.show()

        return final_val
    
    def get_optimal_sweep(self, key_x, step_size, min, max, loss_function):
        initial_val = getattr(self, key_x)

        points = []

        for i in np.arange(min, max, step_size):
            setattr(self, key_x, i * initial_val.units)
            self.run()
            loss = loss_function(self)
            points.append((i, loss))

        setattr(self, key_x, initial_val)

        # Plotting
        x = [point[0] for point in points]
        y = [point[1] for point in points]

        plt.plot(x, y)
        plt.xlabel(key_x)
        plt.ylabel("Loss")
        plt.title(f"{key_x} vs Loss")
        plt.show()

        return x[y.index(min(y))]

def loss_function(model):
    return (model.power_gen - model.power_loss).m ** 2

# Inputs
inputs_dict = {
    # General
    "avg_velocity": 16 * UR.mps, # m/s | average velocity

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

model = VehicleModel(inputs_dict)
# model.get_optimal_sweep("avg_velocity", 0.01, 0, 22, loss_function)
model.get_optimal_gd("lr_incident_angle", loss_function, 1)