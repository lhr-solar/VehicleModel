import math

from models.energy_model import EnergyModel
from typing import override
from pint.facets.plain import PlainQuantity
from pint import Quantity


class SCPDragModel(EnergyModel):
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_wind_modifier(
        wind_speed: float,
        wind_direction: float,
        vehicle_heading: float = 0,
        vehicle_speed: float = 0,
    ) -> float:
        """
        Calculate drag modifier based on relative wind.

        Args:
            wind_speed: Wind speed in m/s (from meteorological convention)
            wind_direction: Direction wind is coming FROM (0=N, 90=E, 180=S, 270=W)
            vehicle_heading: Direction vehicle is heading (0=N, 90=E, 180=S, 270=W)
            vehicle_speed: Vehicle speed in m/s

        Returns:
            Modifier factor for drag coefficient
        """
        if vehicle_speed <= 0:
            return 1.0

        relative_wind_dir = (wind_direction - vehicle_heading) % 360
        headwind_component = wind_speed * math.cos(math.radians(relative_wind_dir))
        relative_speed = vehicle_speed + headwind_component

        if relative_speed < 0:
            relative_speed = 0

        return (relative_speed / vehicle_speed) ** 2

    @override
    def update(
        self, params: dict[str, PlainQuantity[float]], timestep: PlainQuantity[float]
    ) -> PlainQuantity[float]:
        wind_speed = (
            params.get("weather_wind_speed", Quantity(0, "m/s")).to("m/s").magnitude
        )
        wind_direction = params.get(
            "weather_wind_direction", Quantity(0, "degree")
        ).magnitude
        vehicle_heading = params.get("vehicle_heading", Quantity(0, "degree")).magnitude
        vehicle_speed = params["velocity"].to("m/s").magnitude

        wind_modifier = self.get_wind_modifier(
            wind_speed, wind_direction, vehicle_heading, vehicle_speed
        )

        drag_coeff_effective = params["drag_coeff"] * wind_modifier

        params["drag_power"] = -(
            0.5
            * params["air_density"]
            * params["velocity"] ** 3
            * drag_coeff_effective
            * params["frontal_area"]
        ).to("watts")
        return params["drag_power"] * timestep
