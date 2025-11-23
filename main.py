from pint import UnitRegistry, Quantity
from models.base import VehicleModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from typing import TypedDict, cast
import yaml

UNIT_REGISTRY = UnitRegistry()

class YAMLParam(TypedDict):
    name: str
    value: float
    unit: str

def parse_yaml(yaml_path: str) -> dict[str, Quantity[float]]:
    with open(yaml_path, "r") as file:
        data = cast(list[YAMLParam], yaml.safe_load(file))

    result: dict[str, Quantity[float]] = {}

    for param_dict in data:
        result[param_dict['name']] = param_dict['value'] * UNIT_REGISTRY(param_dict['unit'])

    return result

def main():
    m = VehicleModel(parse_yaml("params.yaml"))
    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModel())
  
    m.print_params()
    for i in range(30):
        print("====================")
        m.update()
        m.print_params_diff()

if __name__ == "__main__":
    main()
