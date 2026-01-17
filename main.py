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
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

UNIT_REGISTRY = UnitRegistry()

# Default parameters to log if none specified
DEFAULT_LOG_PARAMS = ["velocity", "total_energy", "array_power"]

class YAMLParam(TypedDict):
    name: str
    value: float
    unit: str

def parse_yaml(yaml_path: str) -> dict[str, datetime | Quantity[float]]:
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
    
    # Get start time from params with default fallback
    current_time = m.params.get("start_ts", datetime(2026, 7, 1, 9, 0, 0))
    timestep_seconds = m.params["timestep"].to("seconds").magnitude
    
    rows: list[dict] = []
    
    # Logging for every timestep
    for i in range(total_steps):
        m.update()
        
        # Store date, time, and datetime object
        row = {
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%H:%M:%S"),
            "datetime": current_time
        }
        
        for name in log_params:
            value = m.params.get(name)
            if isinstance(value, Quantity):
                row[name] = value.magnitude
            else:
                row[name] = value
        
        rows.append(row)
        current_time += timedelta(seconds=timestep_seconds)
    
    return pd.DataFrame(rows)

def get_param_units(m: VehicleModel, params: list[str]) -> dict[str, str]:
    units_map = {}
    for param in params:
        value = m.params.get(param)
        if isinstance(value, Quantity):
            units_map[param] = f"{value.units:~}"  # Compact unit format
        else:
            units_map[param] = "dimensionless"
    
    return units_map

def create_graph(df: pd.DataFrame, param: str, param_unit: str, output_path: str):
    plt.style.use('seaborn-v0_8-darkgrid')
    
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
 
    times = pd.to_datetime(df['datetime'])
    
    # Plot the parameter
    ax.plot(times, df[param], linewidth=2.5, marker='o', 
           markersize=4, markevery=max(1, len(df) // 50), color="#B923AA")
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    
    # Format y-axis label with parameter name and unit
    if param_unit != "dimensionless":
        ylabel = f"{param} ({param_unit})"
    else:
        ylabel = param
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    
    # Title with parameter name
    ax.set_title(f'{param} Over Time', fontsize=14, fontweight='bold', pad=20)
    
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    
    plt.tight_layout()
    
    # Save the figure
    plt.savefig(output_path, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    
    print(f"Graph saved to {output_path}")

def generate_graphs(df: pd.DataFrame, graph_params: list[str], units_map: dict[str, str], output_dir: str):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
  
    missing_params = [p for p in graph_params if p not in df.columns]
    if missing_params:
        print(f"The parameters were not found in the data: {missing_params}")
        graph_params = [p for p in graph_params if p in df.columns]
    
    if not graph_params:
        print("No valid parameters to graph.")
        return
    
    # Create a separate graph for each parameter
    for param in graph_params:
        # Create filename based on parameter name
        filename = f"{param}_graph.png"
        output_file = output_path / filename
        
        # Get unit for this parameter
        param_unit = units_map.get(param, "dimensionless")
        
        create_graph(df, param, param_unit, str(output_file))

def main():
    # Command-line arguments
    parser = argparse.ArgumentParser(description="Run vehicle model and log parameters.")
    parser.add_argument(
        "--log",
        nargs="+",
        help=f"List of parameter names to log each timestep (default: {', '.join(DEFAULT_LOG_PARAMS)})",
        default=DEFAULT_LOG_PARAMS
    )
    parser.add_argument(
        "--csv",
        default="log.csv",
        help="Output CSV filename (default: log.csv)"
    )
    parser.add_argument(
        "--graph",
        nargs="*",
        help="List of parameter names to graph over time (default: graphs all logged parameters)",
        default=None
    )
    parser.add_argument(
        "--graph-output",
        default="output",
        help="Output directory for graphs (default: output/)"
    )
    args = parser.parse_args()
    
    # Initialize vehicle model
    m = VehicleModel(parse_yaml("params.yaml"))
    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModel())
    
    # Determine which parameters to graph (default: all logged parameters)
    graph_params = args.graph or args.log
    
    # Combine log and graph parameters to ensure all needed data is captured
    all_params = list(set(args.log + graph_params))
    
    # Run simulation and get results
    df = run_simulation(m, all_params)
    
    # Get units for all parameters after running simulation
    units_map = get_param_units(m, all_params)
    
    # Save to CSV
    df_to_save = df.drop(columns=['datetime'])  
    df_to_save.to_csv(args.csv, index=False)
    print(f"Simulation complete. Results saved to {args.csv}")
    
    # Generate graphs
    generate_graphs(df, graph_params, units_map, args.graph_output)

if __name__ == "__main__":
    main()