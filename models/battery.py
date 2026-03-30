from models.energy_model import EnergyModel
from typing import override
from pint import Quantity

class ESRBatteryLossModel(EnergyModel):
    def __init__(self):
        pass

    @override
    def update(self, params: dict[str, float], timestep: Quantity[float]) -> Quantity[float]:
        #Pack Resistance
        params['pack_resistance'] = (params['cell_internal_impedance'] / params['cells_in_parallel']) * params['cells_in_series']

        #P = I^2 * R
        params['current_draw'] = (params['drag_power'] + params['rolling_resistance_power'])/params['battery_voltage_nominal']
        params['battery_power_loss'] = (params['current_draw'] ** 2) * params['pack_resistance']
        return -params['battery_power_loss']*timestep
    
class BatteryModel(EnergyModel):

    def __init__(self):
        super().__init__()
        #esr_loss
        self.loss_model = ESRBatteryLossModel()
    
    @override
    def update(self, params: dict[str, float], timestep:Quantity[float]):
        return self.loss_model.update(params, timestep)
        
    

from models.energy_model import EnergyModel
from typing import override
from pint import Quantity

class ESRBatteryLossModel(EnergyModel):
    def __init__(self):
        pass

    @override
    def update(self, params: dict[str, float], timestep: Quantity[float]) -> Quantity[float]:
        #Pack Resistance
        params['pack_resistance'] = (params['cell_internal_impedance'] / params['cells_in_parallel']) * params['cells_in_series']

        #P = I^2 * R
        params['current_draw'] = (params['drag_power'] + params['rr_power'])/params['battery_voltage_nominal']
        params['battery_power_loss'] = (params['current_draw'] ** 2) * params['pack_resistance']
        return -params['battery_power_loss']*timestep
    
class BatteryModel(EnergyModel):

    def __init__(self):
        super().__init__()
        #esr_loss
        self.loss_model = ESRBatteryLossModel()
    
    @override
    def update(self, params: dict[str, float], timestep:Quantity[float]):
        return self.loss_model.update(params, timestep)
        
class CellModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @override
    def update(self, params: dict[str, float], timestep: Quantity[float]) -> Quantity[float]:
        #Circuit Parameters
        R0 = params.get('cell_R0', 0.01)   # Ohms
        R1 = params.get('cell_R1', 0.005)  # Ohms
        C1 = params.get('cell_C1', 1000.0) # Farads
        R2 = params.get('cell_R2', 0.005)  # Ohms
        C2 = params.get('cell_C2', 5000.0) # Farads
        U_oc = params.get('cell_U_oc', 4.2) # Open Circuit Voltage
        
        #Current State Variables
        U1 = params.get('cell_U1', 0.0)
        U2 = params.get('cell_U2', 0.0)

        #Cell current calculation
        # Assuming total power demand is calculated, find the current for a SINGLE cell.
        total_power = params.get('drag_power', 0) + params.get('rr_power', 0)
        pack_current = total_power / params.get('battery_voltage_nominal', 400.0)
        
        #Current per cell = Pack Current / Number of parallel sets
        I_cell = pack_current / params.get('cells_in_parallel', 1)

        # Integration using (Forward Euler)
        dt = timestep.m_as('s') #Convert the timestep to seconds for integration
        
        # C should not be 0 if division happens so included the checking if C1 and C2 are greater than 0 before integration
        dU1 = (-U1 / (R1 * C1) + I_cell / C1) * dt if (R1 * C1) > 0 else 0
        dU2 = (-U2 / (R2 * C2) + I_cell / C2) * dt if (R2 * C2) > 0 else 0
        
        # Update the state variables for next timestep
        params['cell_U1'] = U1 + dU1
        params['cell_U2'] = U2 + dU2

        # Terminal Voltage Calculation
        Ut = U_oc - (I_cell * R0) - params['cell_U1'] - params['cell_U2']
        params['cell_voltage_terminal'] = Ut

        # Power Loss (Internal Resistance + RC losses)
        # P_loss = I^2*R0 + U1^2/R1 + U2^2/R2
        cell_power_loss = (I_cell ** 2) * R0
        if R1 > 0: cell_power_loss += (params['cell_U1'] ** 2) / R1
        if R2 > 0: cell_power_loss += (params['cell_U2'] ** 2) / R2
        
        params['cell_power_loss'] = cell_power_loss

        # Total Pack Loss = Cell Loss * Total number of cells
        total_cells = params.get('cells_in_series', 1) * params.get('cells_in_parallel', 1)
        params['battery_power_loss'] = cell_power_loss * total_cells

        # Return the energy lost over this timestep
       #debug print
        print(f"Ut: {params.get('cell_voltage_terminal'):.2f}V | U1: {params['cell_U1']:.4f}V | U2: {params['cell_U2']:.4f}V")
        return -params['battery_power_loss'] * timestep