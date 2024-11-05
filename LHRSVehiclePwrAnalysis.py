from pint import UnitRegistry
import math
import matplotlib.pyplot as plt

ur = UnitRegistry()

# Constants
# General
avg_velocity = 40 * ur.mph # mph
distance_driven = 40 * ur.miles # miles
drive_eff = 0.95**3

# Drag
drag_coeff = 0.2 # drag coefficient
drag_area = 1.105 * (ur.meter**2) # m^2
air_density = 1.225 * ur.kilogram/(ur.meter**3) # kg/m^3

# Array
array_area = 4 * (ur.meter**2) # m^2 | applicable area for solar array
# cell_eff = 0.24
mppt_eff = 0.985
v_mpp = 0.62 * ur.volts
i_mpp = 6 * ur.amperes

# G = 4.89 * (ur.kilowatt/(ur.meter**2)) #  | irradiance on a horizontal surface
# R = 1 # dimensionless | tilt correction factor
del_t = distance_driven / avg_velocity # hrs | time spent racing

# Aeroshell
maxwidth = 190 * ur.inch # in | max topshell width our facility can fit
maxlength = 62 * ur.inch # in | max topshell length our facility can fit
non_array_area = [1.34 * (ur.meter**2), 2.65 * (ur.meter**2)] # m^2 | upper and lower bound of area on the top-shell not covered by cells

bottomshell_weight = 50.11 * ur.force_pound # lb | 
canopy_weight = 9.29858 * ur.force_pound # lb |
topshell_density = 5.537037037 * (ur.force_pound/(ur.meter**2))# lb/m^2 | area density of top-shell at fixed 4-ply height, fixed resin ratio
long_bulkhead_density = .6992880534 * (ur.force_pound/ur.meter) # lb/m | linear density of longitudinal bulkheads
lat_bulkhead_density = 1.04893208 * (ur.force_pound/ur.meter) # lb/m | linear density of lateral bulkheads
occ_cell_cutout_weight = 5.8017369 * ur.force_pound # lb | weight of the area cutout of the top shell to enable the occupant cell

base_weight = 471.0185 * ur.force_pound # lbs

# Rolling Resistance
mu = 0.00175 # dimensionless | rolling resistance coefficient
mu2 = 0.0000311 * (ur.hour/ur.kilometer) # rolling resistance coefficient wrt velocity

battery_eff = 0.95
frac_soc = 1 # % | fractional state of charge
battery_E_max = 5240 * ur.kilowatt_hour # | fully charged energy of battery


# Functions
def shell_weight(array_area):
    topshell_area = array_area + non_array_area[0]
    width = 1.4 * ur.meter # m
    length = topshell_area / width # m
    topshell_weight = topshell_density*length*width + long_bulkhead_density*length + lat_bulkhead_density*width
    aero_weight = bottomshell_weight + topshell_weight + canopy_weight - occ_cell_cutout_weight
    
    return aero_weight

def pwr_loss(drag_area, 
            weight):
    drag_loss = (drag_coeff * drag_area * 0.5 * air_density * (avg_velocity**2))
    frictional_loss = weight * (mu + (mu2*avg_velocity))

    loss_energy = ((drag_loss + frictional_loss)*distance_driven/drive_eff).to_reduced_units() # in joules (energy)
    loss = (loss_energy/(distance_driven/avg_velocity)).to_reduced_units()

    return loss.to('watts')

def pwr_gen(array_eff,
           array_area,
           v_mpp,
           i_mpp):
    num_cells = math.floor(array_area/(15625 * (ur.mm**2)))
    gen = (array_eff * v_mpp * i_mpp * num_cells).to_reduced_units()
    return gen.to('watts')


def run_model(array_area):
    aero_weight = shell_weight(array_area)

    power_loss = pwr_loss(
        drag_area=drag_area,
        weight=base_weight+aero_weight
    )

    power_gen = pwr_gen(
        array_eff = mppt_eff*(500/938),
        array_area = array_area,
        v_mpp = v_mpp,
        i_mpp = i_mpp
    )

    return power_gen, power_loss

array_areas = []
efficiencies = []

for array_area in range(4000, 6000, 125):
    array_area_m2 = (array_area / 1000) * (ur.meter**2)
    array_areas.append(array_area_m2.magnitude)
    
    model_output = run_model(array_area_m2)
    
    efficiencies.append(model_output[0].magnitude / model_output[1].magnitude)

plt.plot(array_areas, efficiencies)
plt.xlabel('Array Area (m^2)')
plt.ylabel('Efficiency')
plt.title('Efficiency vs Array Area')
plt.grid(True)
plt.show()