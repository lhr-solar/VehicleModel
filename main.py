from pint import UnitRegistry, Quantity
from models.base import VehicleModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from typing import TypedDict, cast
from datetime import datetime
import yaml
import argparse
import pandas as pd

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
    parser = argparse.ArgumentParser(description="Run vehicle model and log parameters.")
    parser.add_argument(
        "--log",
        nargs="+",
        help="List of parameter names to log each timestep",
        required=True
    )
    parser.add_argument(
        "--csv",
        default="log.csv",
        help="Output CSV filename (default: log.csv)"
    )
    args = parser.parse_args()

    m = VehicleModel(parse_yaml("params.yaml"))
    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModel())

    # Total steps
    total_steps = int(
        (m.params["raceday_len"] / m.params["timestep"]).to("dimensionless").magnitude
    )

    rows: list[dict] = []
    t = 0.0
    for i in range(total_steps):
        m.update()

        row = {"timestep": t}
        for name in args.log:
            value = m.params.get(name)
            # Handle pint quantities → convert to base units → numeric
            if isinstance(value, Quantity):
                row[name] = value.magnitude
            else:
                row[name] = value

        rows.append(row)

        # Increment time
        t += m.params["timestep"].to("seconds").magnitude

    df = pd.DataFrame(rows)
    df.to_csv(args.csv, index=False)

if __name__ == "__main__":
    main()
