"""
Contrôle d'une porte d'aération d'une serre (mode simulation PC / Raspberry Pi).

Objectifs :
- Appliquer l'algorithme d'ouverture (température + luminosité) toutes les secondes en mode automatique.
- Permettre un contrôle manuel (entrée %, boutons ouvrir/fermer).
- Préparer la structure capteurs/actionneur (DHT11, photorésistance, ultrason, moteur) tout en simulant
  les valeurs sur PC si RPi.GPIO n'est pas disponible.
"""

from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

from algorithm import clamp
from controller import GreenhouseController, SystemSnapshot
from motor import MotorSimulator
from sensors import SensorManager


class GreenhouseApp(tk.Tk):
    """Interface Tkinter (UI) : affiche l'état et relaie les actions utilisateur vers le contrôleur."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Contrôle d'une porte d'aération d'une serre")
        self.minsize(560, 320)

        self._sensor_manager = SensorManager()
        self._motor = MotorSimulator(initial_opening_percent=0.0)
        self._controller = GreenhouseController(sensor_manager=self._sensor_manager, motor=self._motor)

        self._mode_var = tk.StringVar(value="auto")
        self._manual_percent_var = tk.StringVar(value="56")  # valeur d'exemple du sujet

        self._temperature_var = tk.StringVar(value="--")
        self._luminosity_var = tk.StringVar(value="--")
        self._automatic_opening_var = tk.StringVar(value="--")
        self._motor_state_var = tk.StringVar(value="Arrêt")
        self._motor_direction_var = tk.StringVar(value="--")
        self._distance_var = tk.StringVar(value="--")
        self._speed_var = tk.StringVar(value="0")
        self._opening_var = tk.StringVar(value="0")

        self._build_ui()
        self._apply_mode_to_ui()

        self._last_tick = time.monotonic()
        self.after(200, self._tick)  # premier affichage rapide

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text="Contrôle d'une porte d'aération d'une serre", font=("TkDefaultFont", 14, "bold"))
        title.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")

        info_frame = ttk.Frame(self)
        info_frame.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        info_frame.columnconfigure(0, weight=1)

        ttk.Label(info_frame, text="Température interne ambiante :").grid(row=0, column=0, sticky="w")
        ttk.Label(info_frame, textvariable=self._temperature_var).grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Label(info_frame, text="Intensité lumineuse à l'interne :").grid(row=1, column=0, sticky="w")
        ttk.Label(info_frame, textvariable=self._luminosity_var).grid(row=1, column=1, sticky="w", padx=(8, 0))

        ttk.Label(info_frame, text="Ouverture de la porte automatique :").grid(row=2, column=0, sticky="w")
        ttk.Label(info_frame, textvariable=self._automatic_opening_var).grid(row=2, column=1, sticky="w", padx=(8, 0))

        control_frame = ttk.LabelFrame(self, text="Contrôle")
        control_frame.grid(row=2, column=0, padx=12, pady=8, sticky="ew")
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)

        ttk.Label(control_frame, text="Moteur :").grid(row=0, column=0, sticky="w")
        ttk.Label(control_frame, textvariable=self._motor_state_var).grid(row=0, column=1, sticky="w")
        ttk.Label(control_frame, text="Détecteur de distance :").grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Label(control_frame, textvariable=self._distance_var).grid(row=0, column=3, sticky="w")

        ttk.Label(control_frame, text="Direction :").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(control_frame, textvariable=self._motor_direction_var).grid(row=1, column=1, sticky="w", pady=(2, 0))
        ttk.Label(control_frame, text="Vitesse :").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(2, 0))
        ttk.Label(control_frame, textvariable=self._speed_var).grid(row=1, column=3, sticky="w", pady=(2, 0))

        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self._open_button = ttk.Button(button_frame, text="Ouvrir la porte", command=self._on_open_clicked)
        self._open_button.grid(row=0, column=0, padx=(0, 8))
        self._close_button = ttk.Button(button_frame, text="Fermer la porte", command=self._on_close_clicked)
        self._close_button.grid(row=0, column=1)

        mode_frame = ttk.Frame(self)
        mode_frame.grid(row=3, column=0, padx=12, pady=6, sticky="ew")
        ttk.Label(mode_frame, text="Mode :").grid(row=0, column=0, sticky="w")

        self._auto_rb = ttk.Radiobutton(mode_frame, text="Automatique", value="auto", variable=self._mode_var, command=self._on_mode_changed)
        self._auto_rb.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self._manual_rb = ttk.Radiobutton(mode_frame, text="Manuelle", value="manual", variable=self._mode_var, command=self._on_mode_changed)
        self._manual_rb.grid(row=0, column=2, sticky="w", padx=(8, 0))

        manual_frame = ttk.Frame(self)
        manual_frame.grid(row=4, column=0, padx=12, pady=(2, 12), sticky="ew")
        ttk.Label(manual_frame, text="Ouverture :").grid(row=0, column=0, sticky="w")
        self._manual_entry = ttk.Entry(manual_frame, width=6, textvariable=self._manual_percent_var)
        self._manual_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(manual_frame, text="%").grid(row=0, column=2, sticky="w", padx=(4, 0))
        apply_btn = ttk.Button(manual_frame, text="Appliquer", command=self._on_apply_manual_opening_clicked)
        apply_btn.grid(row=0, column=3, sticky="w", padx=(10, 0))

        ttk.Label(manual_frame, text="Ouverture actuelle :").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(manual_frame, textvariable=self._opening_var).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

        self._manual_frame = manual_frame
        self._manual_entry.bind("<Return>", lambda _event: self._on_apply_manual_opening_clicked())

        self._warnings_var = tk.StringVar(value="")
        self._warnings_frame = ttk.LabelFrame(self, text="Avertissements")
        self._warnings_label = ttk.Label(
            self._warnings_frame,
            textvariable=self._warnings_var,
            wraplength=500,
        )
        self._warnings_label.grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self._warnings_frame.grid(row=5, column=0, padx=12, pady=6, sticky="ew")
        self._warnings_frame.grid_remove()  # caché tant qu'il n'y a pas d'avertissements

        footer = ttk.Label(self, text="Simulation PC" if not self._sensor_manager.is_hardware_available else "Raspberry Pi détecté")
        footer.grid(row=6, column=0, padx=12, pady=(0, 10), sticky="w")

    def _apply_mode_to_ui(self) -> None:
        is_manual = self._mode_var.get() == "manual"
        state = "normal" if is_manual else "disabled"

        # En manuel : entrée + boutons actifs. En auto : on désactive pour éviter la confusion.
        self._manual_entry.configure(state=state)
        self._open_button.configure(state=state)
        self._close_button.configure(state=state)

    def _on_mode_changed(self) -> None:
        self._controller.set_mode(self._mode_var.get())
        self._apply_mode_to_ui()

    def _on_apply_manual_opening_clicked(self) -> None:
        value = self._parse_manual_opening_percent_or_none()
        if value is None:
            self.bell()
            return
        self._controller.set_manual_target_opening_percent(value)

    def _on_open_clicked(self) -> None:
        self._controller.set_target_fully_open()
        self._manual_percent_var.set("100")

    def _on_close_clicked(self) -> None:
        self._controller.set_target_fully_closed()
        self._manual_percent_var.set("0")

    def _parse_manual_opening_percent_or_none(self) -> Optional[float]:
        raw = self._manual_percent_var.get().strip().replace(",", ".")
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        return clamp(value, 0.0, 100.0)

    def _tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now

        # On cadence sur ~1s, mais en gardant une UI fluide.
        snapshot = self._controller.step_once(dt_seconds=clamp(dt, 0.2, 1.2))
        self._refresh_ui(snapshot)

        self.after(1000, self._tick)

    def _refresh_ui(self, snapshot: SystemSnapshot) -> None:
        t = snapshot.readings.temperature_c
        l = snapshot.readings.luminosity_percent
        o_auto = snapshot.automatic_opening_percent

        self._temperature_var.set(f"{t:.1f} °C")
        self._luminosity_var.set(f"{l:.0f} (0-100)")
        self._automatic_opening_var.set(f"{o_auto:.1f} %")

        motor = snapshot.motor_status
        self._motor_state_var.set("En marche" if motor.is_running else "En arrêt")
        self._motor_direction_var.set(motor.direction_label)
        self._speed_var.set(f"{motor.speed_rpm} tour/min")

        self._distance_var.set(f"{snapshot.distance_cm:.0f} cm")
        self._opening_var.set(f"{snapshot.current_opening_percent:.0f} %")

        if snapshot.warnings:
            self._warnings_var.set("\n".join(snapshot.warnings))
            self._warnings_frame.grid(row=5, column=0, padx=12, pady=6, sticky="ew")
        else:
            self._warnings_var.set("")
            self._warnings_frame.grid_remove()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = GreenhouseApp()
    app.mainloop()


if __name__ == "__main__":
    main()

