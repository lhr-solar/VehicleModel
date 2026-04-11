import threading
import traceback
import tkinter as tk
from tkinter import ttk, scrolledtext
import ttkbootstrap as tb  # type: ignore

import matplotlib.dates as mdates
import pandas as pd
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from main import gui_grid_search, parse_yaml, run_waypoint_sim
from units import Q_

PLOT_COLOR = "#23B982"


class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vehicle Model Simulation")
        self.root.geometry("1400x900")

        # Grid search tab state
        self.gs_results = []  # list of (label, df, units_map)
        self.gs_is_running = False
        self._gs_stop_event = threading.Event()
        self.gs_param_rows = []

        # Waypoints tab state
        self.wp_df = None
        self.wp_units_map = {}
        self.wp_is_running = False
        self._wp_stop_event = threading.Event()
        self.wp_rows = []  # list of (time_var, vel_var, frame)

        self.yaml_params = parse_yaml("params.yaml")

        self._create_ui()

    # ── Top-level layout ────────────────────────────────────────────────────

    def _create_ui(self):
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        wp_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(wp_tab, text="Simulation")
        self._create_wp_tab(wp_tab)

        gs_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(gs_tab, text="Grid Search")
        self._create_gs_tab(gs_tab)

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
                unit_var.set(f"{self.yaml_params[name].units:~}")

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
            if bool(df[param].isna().all()):
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

            date = times.dt.date.iloc[0]
            ax.set_xlim(
                float(mdates.date2num(pd.Timestamp(f"{date} 09:00:00"))),
                float(mdates.date2num(pd.Timestamp(f"{date} 17:00:00"))),
            )

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

    # ── Waypoints Tab ───────────────────────────────────────────────────────

    def _create_wp_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # Left: scrollable control panel
        control_container = ttk.Frame(parent)
        control_container.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        canvas = tk.Canvas(control_container, width=400)
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
        ttk.Label(cf, text="Velocity Waypoints", font=("Arial", 14, "bold")).grid(
            row=row, column=0, columnspan=3, pady=10
        )
        row += 1

        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        row += 1

        vel_unit_label = (
            f"{self.yaml_params['velocity'].units:~}"
            if "velocity" in self.yaml_params
            else "mph"
        )
        ttk.Label(cf, text="Time (h)", font=("Arial", 9, "bold")).grid(
            row=row, column=0, padx=5
        )
        ttk.Label(
            cf, text=f"Velocity ({vel_unit_label})", font=("Arial", 9, "bold")
        ).grid(row=row, column=1, padx=5)
        row += 1

        self.wp_rows_container = ttk.Frame(cf)
        self.wp_rows_container.grid(row=row, column=0, columnspan=3, sticky=tk.EW)
        row += 1

        ttk.Button(cf, text="+ Add Waypoint", command=self._wp_add_row).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=5
        )
        row += 1

        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        row += 1

        # Sim timestep
        ttk.Label(cf, text="Sim timestep (s):", font=("Arial", 9)).grid(
            row=row, column=0, sticky=tk.W, pady=2
        )
        self.wp_sim_timestep_entry = ttk.Entry(cf, width=10)
        self.wp_sim_timestep_entry.insert(0, "60")
        self.wp_sim_timestep_entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        row += 1

        # Output params (same as sim tab)
        ttk.Label(cf, text="Output Parameters", font=("Arial", 11, "bold")).grid(
            row=row, column=0, columnspan=3, pady=5
        )
        row += 1
        ttk.Label(cf, text="Select parameters to log & graph:", font=("Arial", 9)).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(5, 2)
        )
        row += 1

        self.wp_log_param_vars = {}
        wp_common_params = [
            "velocity",
            "total_energy",
            "array_power",
            "array_energy",
            "drag_power",
            "rr_power",
            "total_array_energy",
        ]
        for param in wp_common_params:
            var = tk.BooleanVar(
                value=param in ["velocity", "total_energy", "array_power"]
            )
            ttk.Checkbutton(cf, text=param, variable=var).grid(
                row=row, column=0, columnspan=3, sticky=tk.W, pady=1
            )
            self.wp_log_param_vars[param] = var
            row += 1

        ttk.Label(
            cf, text="Custom parameters (comma-separated):", font=("Arial", 9)
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(10, 2))
        row += 1
        self.wp_custom_params_entry = ttk.Entry(cf, width=30)
        self.wp_custom_params_entry.grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        row += 1

        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        row += 1

        # Param overrides
        ttk.Label(cf, text="Simulation Parameters", font=("Arial", 11, "bold")).grid(
            row=row, column=0, columnspan=3, pady=5
        )
        row += 1

        self.wp_param_entries = {}
        param_names = [
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
        for name in param_names:
            if name not in self.yaml_params:
                continue
            ttk.Label(cf, text=f"{name}:").grid(row=row, column=0, sticky=tk.W, pady=2)
            entry_frame = ttk.Frame(cf)
            entry_frame.grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=2)
            entry = ttk.Entry(entry_frame, width=12)
            entry.insert(0, str(self.yaml_params[name].magnitude))
            entry.pack(side=tk.LEFT, padx=(0, 4))
            ttk.Label(
                entry_frame, text=f"{self.yaml_params[name].units:~}", foreground="gray"
            ).pack(side=tk.LEFT)
            self.wp_param_entries[name] = (entry, f"{self.yaml_params[name].units:~}")
            row += 1

        ttk.Separator(cf, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=5
        )
        row += 1

        self.wp_run_button = ttk.Button(
            cf, text="Run Waypoint Sim", command=self._wp_run
        )
        self.wp_run_button.grid(row=row, column=0, sticky=tk.EW, padx=(0, 5), pady=10)
        self.wp_stop_button = ttk.Button(
            cf, text="Stop", command=self._wp_stop, state="disabled"
        )
        self.wp_stop_button.grid(row=row, column=1, sticky=tk.EW, padx=(5, 0), pady=10)
        row += 1

        self.wp_status_label = ttk.Label(cf, text="Status: Ready", foreground="green")
        self.wp_status_label.grid(row=row, column=0, columnspan=3, pady=5)
        row += 1

        ttk.Label(cf, text="Console Output:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        self.wp_console = scrolledtext.ScrolledText(
            cf, width=40, height=8, wrap=tk.WORD
        )
        self.wp_console.grid(row=row, column=0, columnspan=3, sticky=tk.NSEW, pady=5)

        # Add two default waypoints (time in hours)
        self._wp_add_row(default_time="0", default_vel="0")
        self._wp_add_row(default_time="1", default_vel="15")

        # Right: graph area
        graph_frame = ttk.Frame(parent, padding="10")
        graph_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=5, pady=5)
        self.wp_notebook = ttk.Notebook(graph_frame)
        self.wp_notebook.pack(fill=tk.BOTH, expand=True)

    def _wp_add_row(self, default_time="", default_vel=""):
        time_var = tk.StringVar(value=default_time)
        vel_var = tk.StringVar(value=default_vel)

        row_frame = ttk.Frame(self.wp_rows_container)
        row_frame.pack(fill=tk.X, pady=2)

        ttk.Entry(row_frame, textvariable=time_var, width=10).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Entry(row_frame, textvariable=vel_var, width=10).pack(
            side=tk.LEFT, padx=(0, 5)
        )

        row_data = {"frame": row_frame, "time": time_var, "vel": vel_var}
        self.wp_rows.append(row_data)

        ttk.Button(
            row_frame,
            text="x",
            width=2,
            command=lambda r=row_data: self._wp_remove_row(r),
        ).pack(side=tk.LEFT)

    def _wp_remove_row(self, row_data):
        if len(self.wp_rows) <= 2:
            return
        row_data["frame"].destroy()
        self.wp_rows.remove(row_data)

    def _wp_log(self, message):
        self.wp_console.insert(tk.END, f"{message}\n")
        self.wp_console.see(tk.END)
        self.root.update_idletasks()

    def _wp_run(self):
        if self.wp_is_running:
            return

        for tab in self.wp_notebook.tabs():
            self.wp_notebook.forget(tab)
        self.wp_console.delete(1.0, tk.END)
        self._wp_stop_event.clear()
        self.wp_run_button.config(state="disabled")
        self.wp_stop_button.config(state="normal")
        self.wp_status_label.config(text="Status: Running...", foreground="orange")

        thread = threading.Thread(target=self._wp_worker)
        thread.daemon = True
        thread.start()

    def _wp_stop(self):
        if self.wp_is_running:
            self._wp_stop_event.set()
            self.wp_stop_button.config(state="disabled")
            self.wp_status_label.config(text="Status: Stopping...", foreground="orange")

    def _wp_worker(self):
        try:
            self.wp_is_running = True

            # Parse waypoints — time entered in hours, convert to seconds
            waypoints = []
            for r in self.wp_rows:
                try:
                    t_h = float(r["time"].get())
                    v = float(r["vel"].get())
                    waypoints.append((t_h * 3600.0, v))
                except ValueError:
                    self._wp_log("Warning: skipping invalid waypoint row")

            waypoints.sort(key=lambda x: x[0])

            if len(waypoints) < 2:
                self._wp_log("ERROR: Need at least 2 waypoints.")
                self.wp_status_label.config(text="Status: Error", foreground="red")
                return

            try:
                sim_timestep_s = float(self.wp_sim_timestep_entry.get())
            except ValueError:
                sim_timestep_s = 60.0

            self._wp_log(
                f"Running with {len(waypoints)} waypoints, timestep={sim_timestep_s}s..."
            )

            # Collect param overrides
            param_overrides = {}
            for name, (entry, unit) in self.wp_param_entries.items():
                try:
                    param_overrides[name] = Q_(float(entry.get()), unit)
                except ValueError:
                    self._wp_log(f"Warning: Invalid value for {name}, using default")

            log_params = [p for p, var in self.wp_log_param_vars.items() if var.get()]
            custom = self.wp_custom_params_entry.get().strip()
            if custom:
                log_params.extend(p.strip() for p in custom.split(",") if p.strip())
            if not log_params:
                log_params = ["velocity", "total_energy", "array_power"]

            self.wp_df, self.wp_units_map = run_waypoint_sim(
                waypoints,
                log_params,
                param_overrides,
                sim_timestep_s=sim_timestep_s,
                stop_event=self._wp_stop_event,
            )

            if self._wp_stop_event.is_set():
                self._wp_log("Stopped.")
                self.wp_status_label.config(text="Status: Stopped", foreground="gray")
                return

            self._wp_log(f"Done! {len(self.wp_df)} timesteps.")
            self._wp_create_graphs()
            self.wp_status_label.config(text="Status: Complete", foreground="green")

        except Exception as e:
            self._wp_log(f"ERROR: {str(e)}")
            self._wp_log(traceback.format_exc())
            self.wp_status_label.config(text="Status: Error", foreground="red")
        finally:
            self.wp_is_running = False
            self.wp_run_button.config(state="normal")
            self.wp_stop_button.config(state="disabled")

    def _wp_create_graphs(self):
        if self.wp_df is None or self.wp_df.empty:
            return

        times = pd.to_datetime(self.wp_df["datetime"])
        skip = ["date", "time", "datetime"]
        date = times.dt.date.iloc[0]
        x_min = float(mdates.date2num(pd.Timestamp(f"{date} 09:00:00")))
        x_max = float(mdates.date2num(pd.Timestamp(f"{date} 17:00:00")))

        for param in self.wp_df.columns:
            if param in skip:
                continue
            if bool(self.wp_df[param].isna().all()):
                continue

            tab_frame = ttk.Frame(self.wp_notebook)
            self.wp_notebook.add(tab_frame, text=param)

            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)

            ax.plot(
                times,
                self.wp_df[param],
                linewidth=2,
                marker="o",
                markersize=3,
                markevery=max(1, len(self.wp_df) // 50),
                color=PLOT_COLOR,
            )

            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            ax.set_xlim(x_min, x_max)
            fig.autofmt_xdate(rotation=45, ha="right")

            ax.set_xlabel("Time", fontsize=10, fontweight="bold")
            param_unit = self.wp_units_map.get(param, "dimensionless")
            ylabel = (
                f"{param} ({param_unit})" if param_unit != "dimensionless" else param
            )
            ax.set_ylabel(ylabel, fontsize=10, fontweight="bold")
            ax.set_title(f"{param} Over Time", fontsize=12, fontweight="bold", pad=10)
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
