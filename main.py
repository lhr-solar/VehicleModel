from pint import UnitRegistry, Quantity
from models.base import VehicleModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from typing import TypedDict, cast
from datetime import datetime, timedelta
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
    
    result: dict[str, datetime | Quantity[float]] = {}
    for param in data:
        if param['unit'] == 'datetime':
            # Handle if value is already a datetime object or a string
            if isinstance(param['value'], datetime):
                result[param['name']] = param['value']
            else:
                result[param['name']] = datetime.fromisoformat(str(param['value']))
        else:
            result[param['name']] = param['value'] * UNIT_REGISTRY(param['unit'])
    
    return result

def run_simulation(m: VehicleModel, log_params: list[str]) -> pd.DataFrame:
    # Total number of timesteps
    total_steps = int(
        (m.params["raceday_len"] / m.params["timestep"]).to("dimensionless").magnitude
    )
    
    # Get start time from params, default to 12:00 AM if not specified
    if "start_time" in m.params:
        current_time = m.params["start_time"]
    else:
        current_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    timestep_seconds = m.params["timestep"].to("seconds").magnitude
    
    rows: list[dict] = []
    
    # Logging for every timestep
    for i in range(total_steps):
        m.update()
        
        # Format time as HH:MM:SS
        time_str = current_time.strftime("%H:%M:%S")
        row = {"time": time_str}
        # ensure all parameters exist before logging
        for name in log_params:
            value = m.params.get(name)
            if isinstance(value, Quantity):
                row[name] = value.magnitude
            else:
                row[name] = value
        
        rows.append(row)
        current_time += timedelta(seconds=timestep_seconds)
    
    return pd.DataFrame(rows)

def main():
    # Command-line arguments
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
    
    # Run simulation and get results
    df = run_simulation(m, args.log)
    
    # Save to CSV
    df.to_csv(args.csv, index=False)
    print(f"Simulation complete. Results saved to {args.csv}")

if __name__ == "__main__":
    main()