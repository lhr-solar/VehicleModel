import tkinter as tk
from tkinter import ttk, scrolledtext
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
import matplotlib.dates as mdates
from datetime import datetime
import threading
from main import VehicleModel, parse_yaml, run_simulation, get_param_units
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel
from models.battery import BatteryModel
from units import Q_
from matplotlib.backends._backend_tk import NavigationToolbar2Tk


class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vehicle Model Simulation")
        self.root.geometry("1400x900")

        # Data storage
        self.df = None
        self.units_map = {}
        self.is_running = False

        # Create main containers
        self._create_ui()

    def _create_ui(self):
        # Control panel on the left with scrollbar
        control_container = ttk.Frame(self.root)
        control_container.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Canvas and scrollbar for control panel
        canvas = tk.Canvas(control_container, width=400)
        scrollbar = ttk.Scrollbar(
            control_container, orient="vertical", command=canvas.yview
        )
        control_frame = ttk.Frame(canvas, padding="10")

        control_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=control_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Title
        title_label = ttk.Label(
            control_frame, text="Simulation Control", font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=10)

        # Simulation Parameters Section
        row = 1
        ttk.Separator(control_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10
        )
        row += 1

        ttk.Label(
            control_frame, text="Simulation Parameters", font=("Arial", 11, "bold")
        ).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        # Dictionary to store parameter entries
        self.param_entries = {}

        # Define editable parameters with defaults
        sim_params = [
            ("velocity", "20", "mph"),
            ("timestep", "30", "minutes"),
            ("raceday_len", "8", "hours"),
            ("total_energy", "5240", "Wh"),
            ("weight", "328", "kg"),
            ("drag_coeff", "0.141589419", "dimensionless"),
            ("frontal_area", "1.268", "m^2"),
            ("air_density", "1.225", "kg/m^3"),
            ("mu_rr", "0.00175", "dimensionless"),
            ("num_cells", "258", "dimensionless"),
            ("p_mpp", "3.98", "W"),
            ("cell_efficiency", "0.254", "dimensionless"),
        ]

        for param_name, default_val, unit in sim_params:
            # Label
            label_text = f"{param_name}:"
            ttk.Label(control_frame, text=label_text).grid(
                row=row, column=0, sticky=tk.W, pady=2
            )

            # Entry with unit label
            entry_frame = ttk.Frame(control_frame)
            entry_frame.grid(row=row, column=1, sticky=tk.EW, pady=2)

            entry = ttk.Entry(entry_frame, width=15)
            entry.insert(0, default_val)
            entry.pack(side=tk.LEFT, padx=(0, 5))

            ttk.Label(entry_frame, text=unit, foreground="gray").pack(side=tk.LEFT)

            self.param_entries[param_name] = (entry, unit)
            row += 1

        # Logging Parameters Section
        ttk.Separator(control_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10
        )
        row += 1

        ttk.Label(
            control_frame, text="Output Parameters", font=("Arial", 11, "bold")
        ).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        ttk.Label(
            control_frame, text="Select parameters to log & graph:", font=("Arial", 9)
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 2))
        row += 1

        # Checkboxes for common parameters
        self.log_param_vars = {}
        common_params = [
            "velocity",
            "total_energy",
            "array_power",
            "array_energy",
            "drag_power",
            "rr_power",
            "total_array_energy",
        ]

        for param in common_params:
            var = tk.BooleanVar(
                value=param in ["velocity", "total_energy", "array_power"]
            )
            cb = ttk.Checkbutton(control_frame, text=param, variable=var)
            cb.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=1)
            self.log_param_vars[param] = var
            row += 1

        ttk.Label(
            control_frame,
            text="Custom parameters (comma-separated):",
            font=("Arial", 9),
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        row += 1
        self.custom_params_entry = ttk.Entry(control_frame, width=30)
        self.custom_params_entry.grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=5
        )
        row += 1

        # Info label
        info_label = ttk.Label(
            control_frame,
            text="Note: GUI does not modify params.yaml",
            font=("Arial", 8, "italic"),
            foreground="blue",
        )
        info_label.grid(row=row, column=0, columnspan=2, pady=(10, 5))
        row += 1

        # Run button
        self.run_button = ttk.Button(
            control_frame, text="Run Simulation", command=self._run_simulation
        )
        self.run_button.grid(row=row, column=0, columnspan=2, pady=20)
        row += 1

        # Progress indicator
        self.progress_label = ttk.Label(
            control_frame, text="Status: Ready", foreground="green"
        )
        self.progress_label.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        # Console output
        ttk.Label(control_frame, text="Console Output:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        self.console = scrolledtext.ScrolledText(
            control_frame, width=40, height=10, wrap=tk.WORD
        )
        self.console.grid(row=row, column=0, columnspan=2, sticky=tk.NSEW, pady=5)

        # Graph display area on the right
        graph_frame = ttk.Frame(self.root, padding="10")
        graph_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=5, pady=5)

        # Graph notebook for tabs
        self.notebook = ttk.Notebook(graph_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Configure grid weights
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _log(self, message):
        self.console.insert(tk.END, f"{message}\n")
        self.console.see(tk.END)
        self.root.update_idletasks()

    def _run_simulation(self):
        if self.is_running:
            self._log("Simulation already running!")
            return

        # Clear previous graphs
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        self.run_button.config(state="disabled")
        self.progress_label.config(text="Status: Running...", foreground="orange")
        self.console.delete(1.0, tk.END)

        # Run simulation in thread to prevent GUI freezing
        thread = threading.Thread(target=self._simulation_worker)
        thread.daemon = True
        thread.start()

    def _simulation_worker(self):
        try:
            self.is_running = True
            self._log("Initializing vehicle model...")

            # Initialize vehicle model with base params
            params = parse_yaml("params.yaml")

            # Override with GUI values
            self._log("Applying custom parameters from GUI...")
            for param_name, (entry, unit) in self.param_entries.items():
                try:
                    value = float(entry.get())
                    params[param_name] = Q_(value, unit)
                    self._log(f"  {param_name}: {value} {unit}")
                except ValueError:
                    self._log(f"Warning: Invalid value for {param_name}, using default")

            m = VehicleModel(params)
            m.add_model(SCPRollingResistanceModel())
            m.add_model(SCPDragModel())
            m.add_model(SCPArrayModel())
            m.set_battery_model(BatteryModel())

            # Get log parameters from checkboxes
            log_params = [
                param for param, var in self.log_param_vars.items() if var.get()
            ]

            # Add custom parameters
            custom_params = self.custom_params_entry.get().strip()
            if custom_params:
                custom_list = [p.strip() for p in custom_params.split(",") if p.strip()]
                log_params.extend(custom_list)

            if not log_params:
                self._log("Warning: No parameters selected. Using defaults.")
                log_params = ["velocity", "total_energy", "array_power"]

            self._log(f"Running simulation with parameters: {', '.join(log_params)}")

            # Run simulation
            self.df = run_simulation(m, log_params)
            self.units_map = get_param_units(m, log_params)
            self.params = params  # Store for dynamic graph limits

            self._log(f"Simulation complete! Processed {len(self.df)} timesteps")

            # Check for invalid parameters and empty data
            invalid_params = []
            valid_params = []
            for param in log_params:
                if param not in self.df.columns:
                    invalid_params.append(param)
                    self._log(
                        f"ERROR: Parameter '{param}' not found in simulation results!"
                    )
                elif bool(self.df[param].isna().all()):
                    invalid_params.append(param)
                    self._log(
                        f"ERROR: Parameter '{param}' has no data to plot (all values are empty)!"
                    )
                else:
                    valid_params.append(param)

            if invalid_params:
                self._log(
                    f"WARNING: {len(invalid_params)} invalid parameter(s) ignored: {', '.join(invalid_params)}"
                )

            # Create graphs only for valid parameters
            if valid_params:
                self._create_graphs(valid_params)
                self.progress_label.config(
                    text="Status: Complete (with warnings)"
                    if invalid_params
                    else "Status: Complete",
                    foreground="orange" if invalid_params else "green",
                )
                self._log(
                    f"Graphs generated successfully for {len(valid_params)} parameter(s)!"
                )
            else:
                self._log("ERROR: No valid parameters to graph!")
                self.progress_label.config(
                    text="Status: No valid data", foreground="red"
                )

        except Exception as e:
            import traceback

            self._log(f"ERROR: {str(e)}")
            self._log(traceback.format_exc())
            self.progress_label.config(text="Status: Error", foreground="red")

        finally:
            self.is_running = False
            self.run_button.config(state="normal")

    def _create_graphs(self, params):
        if self.df is None or self.df.empty:
            self._log("No data to plot!")
            return

        times = pd.to_datetime(self.df["datetime"])

        for param in params:
            if param not in self.df.columns:
                self._log(f"Warning: Parameter '{param}' not found in data")
                continue

            # Create a frame for this graph
            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=param)

            # Create matplotlib figure
            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)

            # Plot data
            ax.plot(
                times,
                self.df[param],
                linewidth=2,
                marker="o",
                markersize=3,
                markevery=max(1, len(self.df) // 50),
                color="#B923AA",
            )

            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            fig.autofmt_xdate(rotation=45, ha="right")

            # Labels
            ax.set_xlabel("Time", fontsize=10, fontweight="bold")

            param_unit = self.units_map.get(param, "dimensionless")
            if param_unit != "dimensionless":
                ylabel = f"{param} ({param_unit})"
            else:
                ylabel = param
            ax.set_ylabel(ylabel, fontsize=10, fontweight="bold")

            ax.set_title(f"{param} Over Time", fontsize=12, fontweight="bold", pad=10)
            ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

            # Set dynamic y-axis limit for total_energy based on user input
            if (
                param == "total_energy"
                and hasattr(self, "params")
                and "total_energy" in self.params
            ):
                max_energy = self.params["total_energy"].to("Wh").magnitude
                ax.set_ylim(0, max_energy)

            fig.tight_layout()

            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=tab_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Add toolbar
            toolbar = NavigationToolbar2Tk(canvas, tab_frame)
            toolbar.update()


def main():
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
