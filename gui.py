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

from main import gui_run, gui_grid_search
from units import Q_

PLOT_COLOR = "#23B982"


class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vehicle Model Simulation")
        self.root.geometry("1400x900")

        # Simulation tab state
        self.df = None
        self.units_map = {}
        self.is_running = False
        self._stop_event = threading.Event()

        # Grid search tab state
        self.gs_results = []  # list of (label, df, units_map)
        self.gs_is_running = False
        self._gs_stop_event = threading.Event()
        self.gs_param_rows = []

        with open("params.yaml", "r") as f:
            raw = yaml.safe_load(f)
        self.yaml_params = {p["name"]: p for p in raw}

        self._create_ui()

    # ── Top-level layout ────────────────────────────────────────────────────

    def _create_ui(self):
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        sim_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(sim_tab, text="Simulation")
        self._create_sim_tab(sim_tab)

        gs_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(gs_tab, text="Grid Search")
        self._create_gs_tab(gs_tab)

    # ── Simulation Tab ──────────────────────────────────────────────────────

    def _create_sim_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        control_container = ttk.Frame(parent)
        control_container.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

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

        ttk.Label(
            control_frame, text="Simulation Control", font=("Arial", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, pady=10)

        row = 1
        ttk.Separator(control_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10
        )
        row += 1

        ttk.Label(
            control_frame, text="Simulation Parameters", font=("Arial", 11, "bold")
        ).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        self.param_entries = {}
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
            ttk.Label(control_frame, text=f"{param_name}:").grid(
                row=row, column=0, sticky=tk.W, pady=2
            )
            entry_frame = ttk.Frame(control_frame)
            entry_frame.grid(row=row, column=1, sticky=tk.EW, pady=2)
            entry = ttk.Entry(entry_frame, width=15)
            entry.insert(0, default_val)
            entry.pack(side=tk.LEFT, padx=(0, 5))
            ttk.Label(entry_frame, text=unit, foreground="gray").pack(side=tk.LEFT)
            self.param_entries[param_name] = (entry, unit)
            row += 1

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
            ttk.Checkbutton(control_frame, text=param, variable=var).grid(
                row=row, column=0, columnspan=2, sticky=tk.W, pady=1
            )
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

        ttk.Label(
            control_frame,
            text="Note: GUI does not modify params.yaml",
            font=("Arial", 8, "italic"),
            foreground="blue",
        ).grid(row=row, column=0, columnspan=2, pady=(10, 5))
        row += 1

        self.run_button = ttk.Button(
            control_frame, text="Run Simulation", command=self._run_simulation
        )
        self.run_button.grid(row=row, column=0, sticky=tk.EW, padx=(0, 5), pady=20)
        self.stop_button = ttk.Button(
            control_frame, text="Stop", command=self._stop_simulation, state="disabled"
        )
        self.stop_button.grid(row=row, column=1, sticky=tk.EW, padx=(5, 0), pady=20)
        row += 1

        self.progress_label = ttk.Label(
            control_frame, text="Status: Ready", foreground="green"
        )
        self.progress_label.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        ttk.Label(control_frame, text="Console Output:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        self.console = scrolledtext.ScrolledText(
            control_frame, width=40, height=10, wrap=tk.WORD
        )
        self.console.grid(row=row, column=0, columnspan=2, sticky=tk.NSEW, pady=5)

        graph_frame = ttk.Frame(parent, padding="10")
        graph_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=5, pady=5)
        self.notebook = ttk.Notebook(graph_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

    def _log(self, message):
        self.console.insert(tk.END, f"{message}\n")
        self.console.see(tk.END)
        self.root.update_idletasks()

    def _run_simulation(self):
        if self.is_running:
            self._log("Simulation already running!")
            return

        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        self._stop_event.clear()
        self.run_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.progress_label.config(text="Status: Running...", foreground="orange")
        self.console.delete(1.0, tk.END)

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

            if self.df is None:
                return

            self._log(f"Simulation complete! Processed {len(self.df)} timesteps")

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
                    self._log(f"ERROR: Parameter '{param}' has no data to plot!")
                else:
                    valid_params.append(param)

            if invalid_params:
                self._log(
                    f"WARNING: {len(invalid_params)} invalid parameter(s) ignored: {', '.join(invalid_params)}"
                )

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

        times = pd.to_datetime(self.df["datetime"])  # type: ignore[arg-type]

        for param in params:
            if param not in self.df.columns:
                self._log(f"Warning: Parameter '{param}' not found in data")
                continue

            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=param)

            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)

            ax.plot(
                times,
                self.df[param],
                linewidth=2,
                marker="o",
                markersize=3,
                markevery=max(1, len(self.df) // 50),
                color=PLOT_COLOR,
            )

            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            fig.autofmt_xdate(rotation=45, ha="right")

            ax.set_xlabel("Time", fontsize=10, fontweight="bold")

            param_unit = self.units_map.get(param, "dimensionless")
            ylabel = (
                f"{param} ({param_unit})" if param_unit != "dimensionless" else param
            )
            ax.set_ylabel(ylabel, fontsize=10, fontweight="bold")

            ax.set_title(f"{param} Over Time", fontsize=12, fontweight="bold", pad=10)
            ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

            if param == "total_energy" and "total_energy" in self.param_entries:
                try:
                    ax.set_ylim(0, float(self.param_entries["total_energy"][0].get()))
                except ValueError:
                    pass

            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=tab_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            toolbar = NavigationToolbar2Tk(canvas, tab_frame)
            toolbar.update()

    # ── Grid Search Tab ─────────────────────────────────────────────────────

    def _create_gs_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # Left: scrollable control panel
        control_container = ttk.Frame(parent)
        control_container.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        canvas = tk.Canvas(control_container, width=430)
        scrollbar = ttk.Scrollbar(
            control_container, orient="vertical", command=canvas.yview
        )
        cf = ttk.Frame(canvas, padding="10")

        cf.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=cf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0
        ttk.Label(cf, text="Grid Search", font=("Arial", 14, "bold")).grid(
            row=row, column=0, columnspan=2, pady=10
        )
        row += 1

        # Log params
        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10
        )
        row += 1
        ttk.Label(cf, text="Parameters to Log", font=("Arial", 11, "bold")).grid(
            row=row, column=0, columnspan=2, pady=5
        )
        row += 1
        ttk.Label(cf, text="Select parameters to log & graph:", font=("Arial", 9)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W
        )
        row += 1

        self.gs_log_param_vars = {}
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
            ttk.Checkbutton(cf, text=param, variable=var).grid(
                row=row, column=0, columnspan=2, sticky=tk.W, pady=1
            )
            self.gs_log_param_vars[param] = var
            row += 1

        ttk.Label(
            cf, text="Custom parameters (comma-separated):", font=("Arial", 9)
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        row += 1
        self.gs_custom_params_entry = ttk.Entry(cf, width=30)
        self.gs_custom_params_entry.grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=5
        )
        row += 1

        # Search params
        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10
        )
        row += 1
        ttk.Label(cf, text="Search Parameters", font=("Arial", 11, "bold")).grid(
            row=row, column=0, columnspan=2, pady=5
        )
        row += 1
        self.gs_params_container = ttk.Frame(cf)
        self.gs_params_container.grid(row=row, column=0, columnspan=2, sticky=tk.EW)
        row += 1

        ttk.Button(cf, text="+ Add Parameter", command=self._gs_add_param_row).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1

        # Buttons
        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10
        )
        row += 1

        self.gs_run_button = ttk.Button(
            cf, text="Run Grid Search", command=self._run_grid_search
        )
        self.gs_run_button.grid(row=row, column=0, sticky=tk.EW, padx=(0, 5), pady=10)
        self.gs_stop_button = ttk.Button(
            cf, text="Stop", command=self._stop_grid_search, state="disabled"
        )
        self.gs_stop_button.grid(row=row, column=1, sticky=tk.EW, padx=(5, 0), pady=10)
        row += 1

        self.gs_progress_label = ttk.Label(cf, text="Status: Ready", foreground="green")
        self.gs_progress_label.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        ttk.Label(cf, text="Console Output:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        self.gs_console = scrolledtext.ScrolledText(
            cf, width=40, height=8, wrap=tk.WORD
        )
        self.gs_console.grid(row=row, column=0, columnspan=2, sticky=tk.NSEW, pady=5)

        # Add one default param row
        self._gs_add_param_row()

        # Right: config list + graph notebook
        right_frame = ttk.Frame(parent)
        right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=5, pady=5)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        list_frame = ttk.LabelFrame(right_frame, text="Configurations", padding="5")
        list_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        list_frame.columnconfigure(0, weight=1)

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical")
        self.gs_config_listbox = tk.Listbox(
            list_frame, height=6, yscrollcommand=list_scroll.set, selectmode=tk.SINGLE
        )
        list_scroll.config(command=self.gs_config_listbox.yview)
        self.gs_config_listbox.grid(row=0, column=0, sticky=tk.EW)
        list_scroll.grid(row=0, column=1, sticky=tk.NS)
        self.gs_config_listbox.bind("<<ListboxSelect>>", self._gs_on_config_select)

        graph_frame = ttk.Frame(right_frame)
        graph_frame.grid(row=1, column=0, sticky=tk.NSEW)
        graph_frame.rowconfigure(0, weight=1)
        graph_frame.columnconfigure(0, weight=1)

        self.gs_notebook = ttk.Notebook(graph_frame)
        self.gs_notebook.pack(fill=tk.BOTH, expand=True)

    def _gs_add_param_row(self):
        name_var = tk.StringVar()
        start_var = tk.StringVar(value="0")
        stop_var = tk.StringVar(value="10")
        step_var = tk.StringVar(value="1")
        unit_var = tk.StringVar(value="")

        def _on_name_change(*_):
            name = name_var.get().strip()
            if name in self.yaml_params and not unit_var.get():
                unit_var.set(self.yaml_params[name]["unit"])

        name_var.trace_add("write", _on_name_change)

        row_frame = ttk.LabelFrame(self.gs_params_container, padding="3")
        row_frame.pack(fill=tk.X, pady=3)

        row_data = {
            "frame": row_frame,
            "name": name_var,
            "start": start_var,
            "stop": stop_var,
            "step": step_var,
            "unit": unit_var,
        }
        self.gs_param_rows.append(row_data)

        # Line 1: name entry + remove button
        line1 = ttk.Frame(row_frame)
        line1.pack(fill=tk.X)
        ttk.Label(line1, text="Name:").pack(side=tk.LEFT)
        ttk.Entry(line1, textvariable=name_var, width=22).pack(
            side=tk.LEFT, padx=(3, 0)
        )
        ttk.Button(
            line1,
            text="x",
            width=2,
            command=lambda r=row_data: self._gs_remove_param_row(r),
        ).pack(side=tk.RIGHT)

        # Line 2: start / stop / step / unit with inline labels
        line2 = ttk.Frame(row_frame)
        line2.pack(fill=tk.X, pady=(3, 0))
        for label, var, width in [
            ("start", start_var, 6),
            ("stop", stop_var, 6),
            ("step", step_var, 6),
            ("unit", unit_var, 10),
        ]:
            ttk.Label(
                line2, text=f"{label}:", font=("Arial", 8), foreground="gray"
            ).pack(side=tk.LEFT)
            ttk.Entry(line2, textvariable=var, width=width).pack(
                side=tk.LEFT, padx=(0, 6)
            )

    def _gs_remove_param_row(self, row_data):
        if len(self.gs_param_rows) <= 1:
            return
        row_data["frame"].destroy()
        self.gs_param_rows.remove(row_data)

    def _gs_log(self, message):
        self.gs_console.insert(tk.END, f"{message}\n")
        self.gs_console.see(tk.END)
        self.root.update_idletasks()

    def _run_grid_search(self):
        if self.gs_is_running:
            self._gs_log("Grid search already running!")
            return

        self._gs_stop_event.clear()
        self.gs_run_button.config(state="disabled")
        self.gs_stop_button.config(state="normal")
        self.gs_progress_label.config(text="Status: Running...", foreground="orange")
        self.gs_console.delete(1.0, tk.END)
        self.gs_config_listbox.delete(0, tk.END)
        for tab in self.gs_notebook.tabs():
            self.gs_notebook.forget(tab)
        self.gs_results = []

        thread = threading.Thread(target=self._gs_worker)
        thread.daemon = True
        thread.start()

    def _stop_grid_search(self):
        if self.gs_is_running:
            self._gs_stop_event.set()
            self.gs_stop_button.config(state="disabled")
            self.gs_progress_label.config(
                text="Status: Stopping...", foreground="orange"
            )

    def _gs_worker(self):
        try:
            self.gs_is_running = True

            # Collect log params
            log_params = [p for p, var in self.gs_log_param_vars.items() if var.get()]
            custom = self.gs_custom_params_entry.get().strip()
            if custom:
                log_params.extend(p.strip() for p in custom.split(",") if p.strip())
            if not log_params:
                self._gs_log("Warning: No parameters selected. Using defaults.")
                log_params = ["velocity", "total_energy", "array_power"]

            # Collect search params
            search_params = {}
            for row in self.gs_param_rows:
                name = row["name"].get().strip()
                if not name:
                    continue
                try:
                    search_params[name] = (
                        float(row["start"].get()),
                        float(row["stop"].get()),
                        float(row["step"].get()),
                        row["unit"].get().strip() or "dimensionless",
                    )
                except ValueError:
                    self._gs_log(f"Warning: Invalid range for '{name}', skipping")

            if not search_params:
                self._gs_log("ERROR: No valid search parameters defined.")
                self.gs_progress_label.config(text="Status: Error", foreground="red")
                return

            self._gs_log(f"Searching over: {list(search_params.keys())}")
            self._gs_log(f"Logging: {log_params}")

            self.gs_results = gui_grid_search(
                log_params, {}, search_params, self._gs_stop_event
            )

            if self._gs_stop_event.is_set():
                self._gs_log("Grid search stopped by user.")
                self.gs_progress_label.config(text="Status: Stopped", foreground="gray")
                return

            self._gs_log(f"Done! {len(self.gs_results)} configuration(s) completed.")

            for label, _, _ in self.gs_results:
                self.gs_config_listbox.insert(tk.END, label)

            if self.gs_results:
                self.gs_config_listbox.selection_set(0)
                self._gs_display_config(0)

            self.gs_progress_label.config(text="Status: Complete", foreground="green")

        except Exception as e:
            self._gs_log(f"ERROR: {str(e)}")
            self._gs_log(traceback.format_exc())
            self.gs_progress_label.config(text="Status: Error", foreground="red")

        finally:
            self.gs_is_running = False
            self.gs_run_button.config(state="normal")
            self.gs_stop_button.config(state="disabled")

    def _gs_on_config_select(self, event):
        selection = self.gs_config_listbox.curselection()
        if selection and self.gs_results:
            self._gs_display_config(selection[0])

    def _gs_display_config(self, index):
        for tab in self.gs_notebook.tabs():
            self.gs_notebook.forget(tab)

        label, df, units_map = self.gs_results[index]
        times = pd.to_datetime(df["datetime"])
        plot_params = [c for c in df.columns if c not in ("date", "time", "datetime")]

        for param in plot_params:
            if df[param].isna().all():
                continue

            tab_frame = ttk.Frame(self.gs_notebook)
            self.gs_notebook.add(tab_frame, text=param)

            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)

            ax.plot(
                times,
                df[param],
                linewidth=2,
                marker="o",
                markersize=3,
                markevery=max(1, len(df) // 50),
                color=PLOT_COLOR,
            )

            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            fig.autofmt_xdate(rotation=45, ha="right")

            ax.set_xlabel("Time", fontsize=10, fontweight="bold")

            param_unit = units_map.get(param, "dimensionless")
            ylabel = (
                f"{param} ({param_unit})" if param_unit != "dimensionless" else param
            )
            ax.set_ylabel(ylabel, fontsize=10, fontweight="bold")

            ax.set_title(
                f"{param} over Time\n{label}", fontsize=11, fontweight="bold", pad=10
            )
            ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=tab_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            toolbar = NavigationToolbar2Tk(canvas, tab_frame)
            toolbar.update()


def main():
    root = tb.Window(themename="darkly")
    app = SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
