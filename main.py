from pint import UnitRegistry, Quantity
from pint.facets.plain import PlainQuantity
from models.lv_draw_model import LVDrawModel
from models.vehicle_model import VehicleModel
from models.battery import BatteryModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from models.motor_losses import MotorLossModel
from units import UNIT_REGISTRY, Q_

from typing import TypedDict, cast
from datetime import datetime, timedelta
import threading
import yaml
import argparse
import json
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from pathlib import Path
import os
from itertools import product

# Default parameters to log if none specified
DEFAULT_LOG_PARAMS = ("velocity", "total_energy", "array_power")


class YAMLParam(TypedDict):
    name: str
    value: float
    unit: str


def parse_yaml(yaml_path: str) -> dict[str, PlainQuantity[float]]:
    with open(yaml_path, "r") as file:
        data = cast(list[YAMLParam], yaml.safe_load(file))

    result: dict[str, PlainQuantity[float]] = {}
    for param in data:
        if param["unit"] == "datetime":
            # Handle if value is already a datetime object or a string
            if isinstance(param["value"], datetime):
                result[param["name"]] = Q_(param["value"].timestamp(), "seconds")
            else:
                result[param["name"]] = Q_(
                    datetime.fromisoformat(str(param["value"])).timestamp(), "seconds"
                )
        else:
            result[param["name"]] = Q_(param["value"], param["unit"])

    return result


def build_model(params: dict[str, PlainQuantity[float]]) -> VehicleModel:
    m = VehicleModel(params)
    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModel())
    m.add_model(MotorLossModel())
    m.set_battery_model(BatteryModel())
    return m


def run_simulation(
    m: VehicleModel,
    log_params: list[str],
    stop_event: threading.Event | None = None,
) -> pd.DataFrame:
    # Total number of timesteps
    total_steps = int(
        (m.params["raceday_len"] / m.params["timestep"]).to("dimensionless").magnitude
    )

    # Get start time from params with default fallback
    start_ts = m.params.get(
        "start_ts", Q_(datetime(2026, 7, 1, 9, 0, 0).timestamp(), "seconds")
    )
    current_time = datetime.fromtimestamp(start_ts.to("seconds").magnitude)
    timestep_seconds = m.params["timestep"].to("seconds").magnitude

    rows: list[dict] = []

    # Logging for every timestep
    for i in range(total_steps):
        if stop_event is not None and stop_event.is_set():
            break
        current_time += timedelta(seconds=timestep_seconds)

        # seconds since midnight
        sec_since_midnight = (
            current_time.hour * 3600 + current_time.minute * 60 + current_time.second
        )

        # inject timestamp into model params
        m.params["timestamp"] = Q_(sec_since_midnight, "seconds")

        m.update()

        # Store date, time, and datetime object
        row = {
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%H:%M:%S"),
            "datetime": current_time,
        }

        for name in log_params:
            value = m.params.get(name)
            if isinstance(value, Quantity):
                row[name] = value.magnitude
            else:
                row[name] = value

        rows.append(row)

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
    plt.style.use("seaborn-v0_8-darkgrid")

    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)

    times = pd.to_datetime(df["datetime"])

    # Plot the parameter
    ax.plot(
        times,
        df[param],
        linewidth=2.5,
        marker="o",
        markersize=4,
        markevery=max(1, len(df) // 50),
        color="#B923AA",
    )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    ax.set_xlabel("Time", fontsize=12, fontweight="bold")

    # Format y-axis label with parameter name and unit
    if param_unit != "dimensionless":
        ylabel = f"{param} ({param_unit})"
    else:
        ylabel = param
    ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")

    # Title with parameter name
    ax.set_title(f"{param} Over Time", fontsize=14, fontweight="bold", pad=20)

    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    if param == "total_energy":
        ax.set_ylim(0, 5240)

    plt.tight_layout()

    # Save the figure
    plt.savefig(output_path, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close()

    print(f"Graph saved to {output_path}")


def generate_graphs(
    df: pd.DataFrame,
    graph_params: list[str],
    units_map: dict[str, str],
    output_dir: str,
):
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


def grid_search(
    search_params: dict[str, tuple[int, int, int, str]],
    output_dir: str,
    csv_name: str,
    m: VehicleModel,
    graph_params: list[str],
    capture_params: list[str],
):
    keys = list(search_params.keys())
    ranges = [
        [Q_(v, unit) for v in np.arange(start, stop, step)]
        for (start, stop, step, unit) in search_params.values()
    ]
    search_configs = [dict(zip(keys, values)) for values in product(*ranges)]

    for config in search_configs:
        config_output_dir = ""

        for k, v in config.items():
            m.params[k] = v
            config_output_dir += f"{k}_{v:~#P}_"

        config_output_dir = config_output_dir[:-1].replace(" ", "_")
        config_output_dir = output_dir + "/" + config_output_dir

        os.makedirs(config_output_dir, exist_ok=True)

        df = run_simulation(m, capture_params)

        # Get units for all parameters after running simulation
        units_map = get_param_units(m, capture_params)

        # Save to CSV
        df_to_save = df.drop(columns=["datetime"])
        csv_path = Path(config_output_dir) / Path(csv_name)
        df_to_save.to_csv(csv_path, index=False)
        print(f"Simulation complete. Results saved to {csv_path}")

        # Generate graphs
        generate_graphs(df, graph_params, units_map, config_output_dir)


def run_full_sim(
    args, stop_event: threading.Event | None = None
) -> tuple[pd.DataFrame | None, dict[str, str] | None]:
    params = parse_yaml(args.params)

    if hasattr(args, "param_overrides") and args.param_overrides:
        params.update(args.param_overrides)

    m = build_model(params)

    log_params = list(args.log)
    graph_params = list(args.graph) if args.graph is not None else log_params
    capture_params = list(set(log_params + graph_params))

    if args.grid_search is not None:
        search_params = {}
        for item in args.grid_search:
            name, start, stop, step, unit = item.split(":")
            search_params[name] = (float(start), float(stop), float(step), unit)
        grid_search(
            search_params, args.output_dir, args.csv, m, graph_params, capture_params
        )
        return None, None

    df = run_simulation(m, capture_params, stop_event)
    units_map = get_param_units(m, capture_params)

    if stop_event is None or not stop_event.is_set():
        os.makedirs(args.output_dir, exist_ok=True)

        df_to_save = df.drop(columns=["datetime"])
        csv_path = Path(args.output_dir) / Path(args.csv)
        df_to_save.to_csv(csv_path, index=False)
        print(f"Simulation complete. Results saved to {csv_path}")

        units_path = Path(args.output_dir) / "units.json"
        with open(units_path, "w") as f:
            json.dump(units_map, f)

        # Only generate file graphs in CLI mode to avoid matplotlib backend conflicts
        if stop_event is None:
            generate_graphs(df, graph_params, units_map, args.output_dir)

    return df, units_map


def gui_grid_search(
    log_params: list[str],
    param_overrides: dict,
    search_params: dict[str, tuple[float, float, float, str]],
    stop_event: threading.Event | None = None,
) -> list[tuple[str, pd.DataFrame, dict[str, str]]]:
    base_params = parse_yaml("params.yaml")
    if param_overrides:
        base_params.update(param_overrides)

    keys = list(search_params.keys())
    ranges = [
        [Q_(v, unit) for v in np.arange(start, stop, step)]
        for (start, stop, step, unit) in search_params.values()
    ]
    configs = [dict(zip(keys, values)) for values in product(*ranges)]

    results = []
    for config in configs:
        if stop_event and stop_event.is_set():
            break
        config_params = base_params.copy()
        config_params.update(config)
        m = build_model(config_params)
        label = ", ".join(f"{k}={v:~#P}" for k, v in config.items())
        df = run_simulation(m, log_params, stop_event)
        units_map = get_param_units(m, log_params)
        results.append((label, df, units_map))

    return results


def gui_run(
    log_params: list[str],
    param_overrides: dict,
    stop_event: threading.Event | None = None,
) -> tuple[pd.DataFrame | None, dict[str, str] | None]:
    args = argparse.Namespace(
        params="params.yaml",
        log=log_params,
        graph=None,
        csv="log.csv",
        output_dir="output",
        grid_search=None,
        param_overrides=param_overrides,
    )
    return run_full_sim(args, stop_event=stop_event)


def main():
    matplotlib.use("Agg")

    parser = argparse.ArgumentParser(
        description="Run vehicle model and log parameters."
    )
    parser.add_argument(
        "--log",
        nargs="+",
        help=f"List of parameter names to log each timestep (default: {', '.join(DEFAULT_LOG_PARAMS)})",
        default=list(DEFAULT_LOG_PARAMS),
    )
    parser.add_argument(
        "--csv", default="log.csv", help="Output CSV filename (default: log.csv)"
    )
    parser.add_argument(
        "--graph",
        nargs="*",
        help="List of parameter names to graph over time (default: graphs all logged parameters)",
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--grid-search",
        nargs="*",
        help="List of parameter ranges, steps, and units to iterate over. Example: velocity:10:50:1:mph",
        default=None,
    )
    parser.add_argument(
        "--params",
        default="params.yaml",
        help="Path to YAML parameter file (default: params.yaml)",
    )
    args = parser.parse_args()
    run_full_sim(args)


if __name__ == "__main__":
    main()
