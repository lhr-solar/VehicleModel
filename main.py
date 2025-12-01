from typing import TypedDict, cast
from datetime import datetime
from pint import UnitRegistry, Quantity         
from models.base import VehicleModel             
from models.rr import SCPRollingResistanceModel  
from models.drag import SCPDragModel             
from models.array import SCPArrayModelWithIncidence  
import yaml

UNIT_REGISTRY = UnitRegistry()

class YAMLParam(TypedDict):
    name: str
    value: float | str
    unit: str

def parse_yaml(yaml_path: str) -> dict[str, Quantity[float]]:
    with open(yaml_path, "r") as file:
        data = cast(list[YAMLParam], yaml.safe_load(file))

    result: dict[str, Quantity[float]] = {}

    for param in data:
        if param["unit"] == "datetime":
            dt = datetime.fromisoformat(str(param["value"]))
            seconds_since_midnight = (dt - dt.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
            result[param["name"]] = seconds_since_midnight * UNIT_REGISTRY.second
        else:
            result[param["name"]] = float(param["value"]) * UNIT_REGISTRY(param["unit"])

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
