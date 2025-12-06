from pint import UnitRegistry, Quantity
from models.vehicle_model import VehicleModel
from models.battery import BatteryModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from typing import TypedDict, cast
from datetime import datetime
import yaml

UNIT_REGISTRY = UnitRegistry()

class YAMLParam(TypedDict):
    name: str
    value: float
    unit: str

def parse_yaml(yaml_path: str) -> dict[str, Quantity[float]]:
    with open(yaml_path, "r") as file:
        data = cast(list[YAMLParam], yaml.safe_load(file))

    result: dict[str, timestamp | Quantity[float]] = {}

    for param in data:
        if param['unit'] == 'datetime':
            result[param['name']] = datetime.timestamp(param['value'])
        else:
            result[param['name']] = param['value'] * UNIT_REGISTRY(param['unit'])

    return result

def main():
    m = VehicleModel(parse_yaml("params.yaml"))
    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModel())
    m.add_model(BatteryModel())
  
    m.print_params()
    for i in range(int((m.params["raceday_len"]/m.params["timestep"]).to('dimensionless').magnitude)):
        print("====================")
        m.update()
        print(m.params["total_energy"])

if __name__ == "__main__":
    main()
