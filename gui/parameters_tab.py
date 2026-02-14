from typing import Dict, Callable
from pint.facets.plain import PlainQuantity
import tkinter as tk
from tkinter import ttk


class ParametersTab:
    """Reusable parameters tab for simulation parameter management"""

    # Parameters to exclude from GUI (constants loaded from params.yaml)
    EXCLUDED_PARAMETERS = {
        "motor_k_H_default",
        "motor_k_E_default",
        "motor_k_B1_default",
        "motor_k_B2_default",
        "motor_k_D_default",
        "motor_k_S",
        "motor_k_C",
        "motor_k_SW_default",
        "copper_temp_coefficient_alpha",
        "motor_T_ref_default",
        "motor_T_operating_default",
        "motor_R_A",
        "motor_R_B",
        "motor_eta_C",
    }

    def __init__(
        self, parent, params: Dict[str, PlainQuantity[float]], on_update: Callable
    ):
        self.params = params
        self.on_update = on_update
        self.frame = ttk.Frame(parent)
        self.entries = {}
        self._build_ui()

    def _build_ui(self):
        """Build the parameters UI"""
        # Create scrollable frame
        canvas = tk.Canvas(self.frame)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Add parameter inputs
        for key, value in self.params.items():
            if key not in self.EXCLUDED_PARAMETERS:
                self._add_parameter_input(scrollable_frame, key, value)

        # Add update button
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(
            btn_frame, text="Update Parameters", command=self._update_params
        ).pack()

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _add_parameter_input(self, parent, key: str, value: PlainQuantity[float]):
        """Add a parameter input field"""
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=5, pady=2)

        ttk.Label(row, text=f"{key}:", width=25).pack(side="left")
        entry = ttk.Entry(row, width=15)
        entry.insert(0, str(value))
        entry.pack(side="left", padx=5)

        ttk.Label(row, text=str(value.units)).pack(side="left")

        self.entries[key] = entry

    def _update_params(self):
        """Update parameters from entries"""
        for key, entry in self.entries.items():
            try:
                value = float(entry.get())
                self.params[key] = self.params[key].__class__(
                    value, self.params[key].units
                )
            except ValueError:
                pass
        self.on_update()

    def get_frame(self):
        """Return the frame for packing"""
        return self.frame
