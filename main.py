from pint import UnitRegistry, Quantity
from models.base import VehicleModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModelWithIncidence  
from typing import TypedDict, cast, Union
from datetime import datetime
import yaml

UNIT_REGISTRY = UnitRegistry()

class YAMLParam(TypedDict):
    name: str
    value: float | str
    unit: str

#  params can be pint Quantities OR datetimes
ParamValue = Union[Quantity[float], datetime]

def parse_yaml(yaml_path: str) -> dict[str, ParamValue]:
    with open(yaml_path, "r") as file:
        data = cast(list[YAMLParam], yaml.safe_load(file))

    result: dict[str, ParamValue] = {}

    for param in data:
        if param["unit"] == "datetime":
            # parse into a datetime object
            result[param["name"]] = datetime.fromisoformat(str(param["value"]))
        else:
            result[param["name"]] = param["value"] * UNIT_REGISTRY(param["unit"])

    return result

def main():
    init_params = parse_yaml("params.yaml")
    init_params["timestamp"] = init_params.pop("start_ts")
    init_params["total_array_energy"] = 0 * UNIT_REGISTRY.joule
    m = VehicleModel(init_params)

    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModelWithIncidence())   

    m.print_params()

    # number of timesteps in the race
    n_steps = int(
        (m.params["raceday_len"] / m.params["timestep"])
        .to("dimensionless")
        .magnitude
    )

    for i in range(n_steps):
        print("====================")
        m.update()

        
        print("total_array_energy:", m.params["total_array_energy"])

if __name__ == "__main__":
    main()
