# VehicleModel
## Setup
We use `uv` as our package manager, so whatever OS you are running, install `uv` [as according to the documentation](https://docs.astral.sh/uv/getting-started/installation/). Then, in the repo directory, run `uv sync` to sync the dependencies in the virtual environment.

## Usage
```
./run-model
options:
  -h, --help            show this help message and exit
  --log LOG [LOG ...]   List of parameter names to log each timestep
                        (default: velocity, total_energy, array_power)
  --csv CSV             Output CSV filename (default: log.csv)
  --graph [GRAPH ...]   List of parameter names to graph over time (default:
                        graphs all logged parameters)
  --graph-output GRAPH_OUTPUT
                        Output directory for graphs (default: output/)
```

