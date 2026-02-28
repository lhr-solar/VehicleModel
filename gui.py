import threading
import traceback
import tkinter as tk
from tkinter import ttk, scrolledtext
import ttkbootstrap as tb  # type: ignore

import matplotlib.dates as mdates
import pandas as pd
import yaml
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from main import gui_run
from units import Q_


class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vehicle Model Simulation")
        self.root.geometry("1400x900")

        # Data storage
        self.df = None
        self.units_map = {}
        self.is_running = False
        self._stop_event = threading.Event()

        # Load params from yaml for GUI defaults
        with open("params.yaml", "r") as f:
            raw = yaml.safe_load(f)
        self.yaml_params = {p["name"]: p for p in raw}

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

        # Editable parameters pulled from params.yaml
        param_names = [
            "velocity",
            "timestep",
            "raceday_len",
            "total_energy",
            "weight",
            "drag_coeff",
            "frontal_area",
            "air_density",
            "mu_rr",
            "num_cells",
            "p_mpp",
            "cell_efficiency",
        ]
        sim_params = [
            (name, str(self.yaml_params[name]["value"]), self.yaml_params[name]["unit"])
            for name in param_names
            if name in self.yaml_params
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

        # Run / Stop buttons
        self.run_button = ttk.Button(
            control_frame, text="Run Simulation", command=self._run_simulation
        )
        self.run_button.grid(row=row, column=0, sticky=tk.EW, padx=(0, 5), pady=20)
        self.stop_button = ttk.Button(
            control_frame,
            text="Stop",
            command=self._stop_simulation,
            state="disabled",
        )
        self.stop_button.grid(row=row, column=1, sticky=tk.EW, padx=(5, 0), pady=20)
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

        self._stop_event.clear()
        self.run_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.progress_label.config(text="Status: Running...", foreground="orange")
        self.console.delete(1.0, tk.END)

        # Run simulation in thread to prevent GUI freezing
        thread = threading.Thread(target=self._simulation_worker)
        thread.daemon = True
        thread.start()

    def _stop_simulation(self):
        if self.is_running:
            self._stop_event.set()
            self.stop_button.config(state="disabled")
            self.progress_label.config(text="Status: Stopping...", foreground="orange")

    def _collect_log_params(self):
        log_params = [p for p, var in self.log_param_vars.items() if var.get()]
        custom_params = self.custom_params_entry.get().strip()
        if custom_params:
            log_params.extend(p.strip() for p in custom_params.split(",") if p.strip())
        if not log_params:
            self._log("Warning: No parameters selected. Using defaults.")
            log_params = ["velocity", "total_energy", "array_power"]
        return log_params

    def _collect_param_overrides(self):
        param_overrides = {}
        for param_name, (entry, unit) in self.param_entries.items():
            try:
                param_overrides[param_name] = Q_(float(entry.get()), unit)
            except ValueError:
                self._log(f"Warning: Invalid value for {param_name}, using default")
        return param_overrides

    def _simulation_worker(self):
        try:
            self.is_running = True
            log_params = self._collect_log_params()
            param_overrides = self._collect_param_overrides()
            self._log(f"Running simulation with parameters: {', '.join(log_params)}")

            self.df, units_map = gui_run(log_params, param_overrides, self._stop_event)
            self.units_map = units_map or {}

            if self._stop_event.is_set():
                self._log("Simulation stopped by user.")
                self.progress_label.config(text="Status: Stopped", foreground="gray")
                return

            if self.df is None or self.units_map is None:
                return

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
            self._log(f"ERROR: {str(e)}")
            self._log(traceback.format_exc())
            self.progress_label.config(text="Status: Error", foreground="red")

        finally:
            self.is_running = False
            self.run_button.config(state="normal")
            self.stop_button.config(state="disabled")

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
            if param == "total_energy" and "total_energy" in self.param_entries:
                try:
                    ax.set_ylim(0, float(self.param_entries["total_energy"][0].get()))
                except ValueError:
                    pass

            fig.tight_layout()

            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=tab_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Add toolbar
            toolbar = NavigationToolbar2Tk(canvas, tab_frame)
            toolbar.update()


def main():
    root = tb.Window(themename="darkly")
    app = SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
