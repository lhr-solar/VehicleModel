from models.base import VehicleModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
import yaml

def parse_yaml(yaml_path: str) -> dict[str, float]:
    with open(yaml_path, "r") as file:
        data = yaml.safe_load(file)

    result: dict[str, float] = {}

    for key, value in data.items():
        try:
            result[key] = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Value for {key!r} is not convertible to float.")

    return result

def main():
    m = VehicleModel(parse_yaml("params.yaml"))
    m.add_model(SCPRollingResistanceModel())
    m.add_model(SCPDragModel())
    m.add_model(SCPArrayModel())
    
    m.print_params()
    m.update()
    print("====================")
    m.print_params()

if __name__ == "__main__":
    main()
