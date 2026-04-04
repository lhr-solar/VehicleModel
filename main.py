from pint import Quantity
from pint.facets.plain import PlainQuantity
from models.vehicle_model import VehicleModel
from models.battery import BatteryModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from models.motor_losses import MotorLossModel
from models.weather_model import WeatherAPI
from units import Q_

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
from scipy.interpolate import PchipInterpolator
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


def run_waypoint_sim(
    waypoints: list[tuple[float, float]],
    log_params: list[str],
    param_overrides: dict,
    sim_timestep_s: float = 60.0,
    stop_event: threading.Event | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Run simulation with a cubic spline velocity profile from (time_s, velocity) waypoints."""
    params = parse_yaml("params.yaml")
    params.update(param_overrides)

    times_wp = np.array([t for t, _ in waypoints])
    vels_wp = np.array([v for _, v in waypoints])
    spline = PchipInterpolator(times_wp, vels_wp)
    vel_unit = params["velocity"].units

    m = build_model(params)
    m.params["timestep"] = Q_(sim_timestep_s, "seconds")

    # Always run to 5 PM (8 hours after 9 AM start)
    race_duration_s = params["raceday_len"].to("seconds").magnitude
    total_steps = int(race_duration_s / sim_timestep_s)
    last_vel = float(spline(times_wp[-1]))

    start_ts = m.params.get(
        "start_ts", Q_(datetime(2026, 7, 1, 9, 0, 0).timestamp(), "seconds")
    )
    current_time = datetime.fromtimestamp(start_ts.to("seconds").magnitude)

    all_log_params = list(set(log_params + ["velocity"]))

    rows: list[dict] = []
    for i in range(total_steps):
        if stop_event is not None and stop_event.is_set():
            break

        t = times_wp[0] + i * sim_timestep_s
        velocity = float(spline(t)) if t <= times_wp[-1] else last_vel

        m.params["velocity"] = Q_(velocity, vel_unit)

        current_time += timedelta(seconds=sim_timestep_s)
        sec_since_midnight = (
            current_time.hour * 3600 + current_time.minute * 60 + current_time.second
        )
        m.params["timestamp"] = Q_(sec_since_midnight, "seconds")

        m.update()

        row: dict = {
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%H:%M:%S"),
            "datetime": current_time,
        }
        for name in all_log_params:
            value = m.params.get(name)
            if isinstance(value, Quantity):
                row[name] = value.magnitude
            else:
                row[name] = value
        rows.append(row)

    df = pd.DataFrame(rows)
    units_map = get_param_units(m, all_log_params)
    return df, units_map


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

    # Initialize weather model if enabled
    if m.params.get("use_weather_data", Q_(0, "dimensionless")).magnitude > 0:
        try:
            weather_model = WeatherAPI()
            latitude = m.params["latitude_deg"].magnitude
            longitude = m.params["longitude_deg"].magnitude

            # Calculate end time
            end_time = current_time + timedelta(seconds=timestep_seconds * total_steps)

            print(
                f"Fetching weather data for {latitude}, {longitude} from {current_time} to {end_time}..."
            )
            weather_model.fetch_weather_data(
                latitude, longitude, current_time, end_time
            )
            m.set_weather_model(weather_model)
            print("Weather data loaded successfully")
        except Exception as e:
            print(
                f"Warning: Failed to load weather data: {str(e)}. Continuing without weather effects."
            )

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
        m.params["current_time_ts"] = Q_(current_time.timestamp(), "seconds")

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

    df = pd.DataFrame(rows)

    if m.weather_model is not None:
        create_weather_graph(df, "output")

    return df


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


def create_weather_graph(df: pd.DataFrame, output_dir: str = "output"):
    """Create a 2x2 panel graph showing all weather variables over time."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    weather_params = [
        "weather_temperature",
        "weather_cloud_cover",
        "weather_wind_speed",
        "weather_wind_direction",
    ]

    # Check if weather data exists
    available_params = [p for p in weather_params if p in df.columns]
    if not available_params:
        print("No weather data available to graph")
        return

    plt.style.use("seaborn-v0_8-darkgrid")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "Weather Conditions Over Race Duration", fontsize=16, fontweight="bold"
    )

    weather_config = {
        "weather_temperature": {"ylabel": "Temperature (°C)", "color": "#FF6B6B"},
        "weather_cloud_cover": {"ylabel": "Cloud Cover (%)", "color": "#4ECDC4"},
        "weather_wind_speed": {"ylabel": "Wind Speed (m/s)", "color": "#45B7D1"},
        "weather_wind_direction": {"ylabel": "Wind Direction (°)", "color": "#96CEB4"},
    }

    for idx, param in enumerate(weather_params):
        if param not in df.columns:
            continue

        ax = axes[idx // 2, idx % 2]
        config = weather_config[param]

        ax.plot(
            df["datetime"],
            df[param],
            marker="o",
            linestyle="-",
            linewidth=2,
            markersize=4,
            color=config["color"],
            markevery=max(1, len(df) // 20),
        )

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        ax.set_xlabel("Time", fontsize=11, fontweight="bold")
        ax.set_ylabel(config["ylabel"], fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    plt.tight_layout()

    output_file = output_path / "weather_conditions.png"
    plt.savefig(
        output_file, bbox_inches="tight", facecolor="white", edgecolor="none", dpi=150
    )
    plt.close()

    print(f"Weather graph saved to {output_file}")


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
    search_params: dict[str, tuple[float, float, float, str]],
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

    if hasattr(args, "waypoints") and args.waypoints is not None:
        waypoints = []
        for wp in args.waypoints:
            t_str, v_str = wp.split(":")
            waypoints.append((float(t_str) * 3600.0, float(v_str)))
        waypoints.sort(key=lambda x: x[0])
        sim_timestep = getattr(args, "sim_timestep", 60.0)
        df, units_map = run_waypoint_sim(
            waypoints, capture_params, {}, sim_timestep_s=sim_timestep
        )
    else:
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
    parser.add_argument(
        "--waypoints",
        nargs="+",
        help="Velocity waypoints as time_hours:velocity pairs. Example: 0:0 1:15 3:40 8:20",
        default=None,
    )
    parser.add_argument(
        "--sim-timestep",
        type=float,
        default=60.0,
        help="Simulation timestep in seconds for waypoint mode (default: 60)",
    )
    args = parser.parse_args()
    run_full_sim(args)


if __name__ == "__main__":
    main()
