from pint import UnitRegistry, Quantity
from pint.facets.plain import PlainQuantity
from models.lv_draw_model import LVDrawModel
from models.vehicle_model import VehicleModel
from models.battery import BatteryModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from models.motor_losses import MotorLossModel
from models.weather_model import WeatherModel
from units import UNIT_REGISTRY, Q_

from typing import TypedDict, cast
from datetime import datetime, timedelta
import yaml
import argparse
import pandas as pd
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


def run_simulation(m: VehicleModel, log_params: list[str]) -> pd.DataFrame:
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
    weather_model = None
    if m.params.get("use_weather_data", Q_(0, "dimensionless")).magnitude > 0:
        try:
            weather_model = WeatherModel()
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
            print("Weather data loaded successfully")
        except Exception as e:
            print(
                f"Warning: Failed to load weather data: {str(e)}. Continuing without weather effects."
            )
            weather_model = None

    rows: list[dict] = []

    # Logging for every timestep
    for i in range(total_steps):
        # seconds since midnight
        sec_since_midnight = (
            current_time.hour * 3600 + current_time.minute * 60 + current_time.second
        )

        # inject timestamp into model params
        m.params["timestamp"] = Q_(sec_since_midnight, "seconds")

        # Apply weather modifiers if available
        if weather_model is not None:
            weather = weather_model.get_weather_at_time(current_time)

            # Temperature modifier (affects battery capacity)
            temp_mod = weather_model.get_temperature_modifier(weather["temperature"])
            m.params["weather_temp_modifier"] = Q_(temp_mod, "dimensionless")

            # Cloud cover modifier (affects array)
            if (
                m.params.get(
                    "weather_cloud_modifier_enabled", Q_(1, "dimensionless")
                ).magnitude
                > 0
            ):
                cloud_mod = weather_model.get_cloud_cover_modifier(
                    weather["cloud_cover"]
                )
                m.params["weather_cloud_modifier"] = Q_(cloud_mod, "dimensionless")

            # Wind modifier (affects drag)
            if (
                m.params.get(
                    "weather_wind_modifier_enabled", Q_(1, "dimensionless")
                ).magnitude
                > 0
            ):
                heading = m.params.get("vehicle_heading", Q_(0, "degree")).magnitude
                vehicle_speed = m.params["velocity"].to("m/s").magnitude
                wind_mod = weather_model.get_wind_modifier(
                    weather["wind_speed"], weather["wind_direction"], heading, vehicle_speed
                )
                m.params["weather_wind_modifier"] = Q_(wind_mod, "dimensionless")

            # Road condition modifier (affects rolling resistance)
            road_mod = weather_model.get_rolling_resistance_modifier(
                weather["precipitation"]
            )
            m.params["weather_road_modifier"] = Q_(road_mod, "dimensionless")

            # Store weather data for logging
            m.params["weather_temperature"] = Q_(weather["temperature"], "celsius")
            m.params["weather_cloud_cover"] = Q_(
                weather["cloud_cover"], "dimensionless"
            )
            m.params["weather_wind_speed"] = Q_(weather["wind_speed"], "m/s")
            m.params["weather_wind_direction"] = Q_(weather["wind_direction"], "degree")

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

        current_time += timedelta(seconds=timestep_seconds)

    df = pd.DataFrame(rows)
    
    # Create weather graph if weather data was used
    if weather_model is not None and weather_model.weather_data is not None:
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

    plt.tight_layout()

    # Save the figure
    plt.savefig(output_path, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close()

    print(f"Graph saved to {output_path}")


def create_weather_graph(df: pd.DataFrame, output_dir: str = "output"):
    """Create a 2x2 panel graph showing all weather variables over time."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    weather_params = ["weather_temperature", "weather_cloud_cover", "weather_wind_speed", "weather_wind_direction"]
    
    # Check if weather data exists
    available_params = [p for p in weather_params if p in df.columns]
    if not available_params:
        print("No weather data available to graph")
        return
    
    plt.style.use("seaborn-v0_8-darkgrid")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Weather Conditions Over Race Duration", fontsize=16, fontweight="bold")
    
    weather_config = {
        "weather_temperature": {"ylabel": "Temperature (°C)", "color": "#FF6B6B"},
        "weather_cloud_cover": {"ylabel": "Cloud Cover (%)", "color": "#4ECDC4"},
        "weather_wind_speed": {"ylabel": "Wind Speed (m/s)", "color": "#45B7D1"},
        "weather_wind_direction": {"ylabel": "Wind Direction (°)", "color": "#96CEB4"}
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
            markevery=max(1, len(df) // 20)
        )
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
        
        ax.set_xlabel("Time", fontsize=11, fontweight="bold")
        ax.set_ylabel(config["ylabel"], fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)
    
    plt.tight_layout()
    
    output_file = output_path / "weather_conditions.png"
    plt.savefig(output_file, bbox_inches="tight", facecolor="white", edgecolor="none", dpi=150)
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
        config_output_dir = os.path.join(output_dir, "grid_search")

        for k, v in config.items():
            m.params[k] = v
            subdir = f"{os.path.basename(k)}_{v:~#P}".replace(" ", "_")
            config_output_dir = os.path.join(config_output_dir, subdir)

        os.makedirs(config_output_dir, exist_ok=True)

        df = run_simulation(m, capture_params)

        # Get units for all parameters after running simulation
        units_map = get_param_units(m, capture_params)

        # Save to CSV
        df_to_save = df.drop(columns=["datetime"])
        csv_path = Path(config_output_dir) / Path(csv_name).name
        df_to_save.to_csv(csv_path, index=False)
        print(f"Simulation complete. Results saved to {csv_path}")

        # Generate graphs
        generate_graphs(df, graph_params, units_map, config_output_dir)

        m.reset()


def main():
    # Command-line arguments
    parser = argparse.ArgumentParser(
        description="Run vehicle model and log parameters."
    )
    parser.add_argument(
        "--log",
        nargs="+",
        help=f"List of parameter names to log each timestep (default: {', '.join(DEFAULT_LOG_PARAMS)})",
        default=DEFAULT_LOG_PARAMS,
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
    args = parser.parse_args()

    # Initialize vehicle model

    m = VehicleModel(parse_yaml("params.yaml"))
    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModel())
    m.add_model(MotorLossModel())
    m.set_battery_model(BatteryModel())

    # Determine which parameters to graph (default: all logged parameters)
    graph_params = args.graph or args.log

    # Combine log and graph parameters to ensure all needed data is captured
    capture_params = list(set(args.log + graph_params))

    if args.grid_search is not None:
        search_params = {}

        for item in args.grid_search:
            try:
                name, start, stop, step, unit = item.split(":")
                search_params[name] = (float(start), float(stop), float(step), unit)
            except ValueError:
                print(
                    f"Warning: Skipping invalid grid search parameter '{item}'. Expected format 'name:start:stop:step:unit'."
                )

        grid_search(
            search_params,
            args.output_dir,
            args.csv,
            m,
            graph_params,
            capture_params,
        )
    else:
        # Run simulation and get results
        df = run_simulation(m, capture_params)

        # Get units for all parameters after running simulation
        units_map = get_param_units(m, capture_params)

        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)

        # Save to CSV
        df_to_save = df.drop(columns=["datetime"])
        csv_path = Path(args.output_dir) / Path(args.csv).name
        df_to_save.to_csv(csv_path, index=False)
        print(f"Simulation complete. Results saved to {csv_path}")

        # Generate graphs
        generate_graphs(df, graph_params, units_map, args.output_dir)


if __name__ == "__main__":
    main()
