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

        # Cadre avec bordure bleu foncé
        border_frame = tk.Frame(self, bg="#1e3a5f", padx=2, pady=2)
        border_frame.grid(row=0, column=0, sticky="nsew")
        border_frame.columnconfigure(0, weight=1)

        main_frame = ttk.Frame(border_frame, padding=12)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)

        title = ttk.Label(main_frame, text="Contrôle d'une porte d'aération d'une serre", font=("TkDefaultFont", 14, "bold"))
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # ----- Section haute : gauche (infos) | droite (mode + barre ouverture) -----
        top_row = ttk.Frame(main_frame)
        top_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=0)

        self._build_top_left_block(top_row)
        self._build_top_right_block(top_row)

        # ----- Section milieu : Contrôle + bouton Automatique, puis cadre Manuelle -----
        self._build_control_section(main_frame)

        # ----- Section basse : Moteur/Direction (gauche) | Détecteur/Vitesse (droite) -----
        self._build_bottom_section(main_frame)

        self._manual_entry.bind("<Return>", lambda _event: self._on_apply_manual_opening_clicked())

        self._warnings_var = tk.StringVar(value="")
        self._warnings_frame = ttk.LabelFrame(main_frame, text="Avertissements")
        self._warnings_label = ttk.Label(
            self._warnings_frame,
            textvariable=self._warnings_var,
            wraplength=500,
        )
        self._warnings_label.grid(row=5, column=0, padx=8, pady=4, sticky="w")
        self._warnings_frame.grid(row=5, column=0, columnspan=2, padx=0, pady=6, sticky="ew")
        self._warnings_frame.grid_remove()

        footer = ttk.Label(main_frame, text="Simulation PC" if not self._sensor_manager.is_hardware_available else "Raspberry Pi détecté")
        footer.grid(row=6, column=0, columnspan=2, pady=(0, 0), sticky="w")

    def _build_top_left_block(self, parent: ttk.Frame) -> None:
        """Bloc gauche du haut : température, luminosité, ouverture automatique."""
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nw")
        ttk.Label(left, text="Température interne ambiante :").grid(row=0, column=0, sticky="w")
        ttk.Label(left, textvariable=self._temperature_var).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(left, text="Intensité lumineuse à l'interne :").grid(row=1, column=0, sticky="w")
        ttk.Label(left, textvariable=self._luminosity_var).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Label(left, text="Ouverture de la porte automatique :").grid(row=2, column=0, sticky="w")
        ttk.Label(left, textvariable=self._automatic_opening_var).grid(row=2, column=1, sticky="w", padx=(8, 0))

    def _build_top_right_block(self, parent: ttk.Frame) -> None:
        """Bloc droit du haut : Mode Manuelle | Automatique, barre d'ouverture verticale, Ouverture %."""
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nw", padx=(24, 0))

        mode_label = ttk.Label(right, text="Mode :")
        mode_label.grid(row=0, column=0, sticky="w")
        self._mode_display_var = tk.StringVar(value="Manuelle | Automatique")
        ttk.Label(right, textvariable=self._mode_display_var).grid(row=0, column=1, sticky="w", padx=(8, 0))

        # Barre d'ouverture verticale type "pile" (segments)
        self._opening_canvas = tk.Canvas(right, width=32, height=72, bg="white", highlightthickness=1, highlightbackground="gray")
        self._opening_canvas.grid(row=1, column=0, columnspan=2, pady=(6, 4))
        self._draw_opening_bar(0.0)

        ttk.Label(right, text="Ouverture :").grid(row=2, column=0, sticky="w", pady=(0, 0))
        ttk.Label(right, textvariable=self._opening_var).grid(row=2, column=1, sticky="w", padx=(8, 0))

    def _draw_opening_bar(self, percent: float) -> None:
        """Dessine la barre d'ouverture verticale avec segments (style pile)."""
        c = self._opening_canvas
        c.delete("all")
        w, h = 32, 72
        n_segments = 5
        segment_h = h / n_segments
        filled_height = (percent / 100.0) * h
        for i in range(n_segments):
            y_top = h - (i + 1) * segment_h
            y_bot = h - i * segment_h
            seg_top, seg_bot = y_top + 2, y_bot - 2
            if filled_height >= y_bot:
                fill = "#e6c229"
                c.create_rectangle(4, seg_top, w - 4, seg_bot, outline="gray", fill=fill)
            elif filled_height <= y_top:
                fill = "#e0e0e0"
                c.create_rectangle(4, seg_top, w - 4, seg_bot, outline="gray", fill=fill)
            else:
                c.create_rectangle(4, seg_top, w - 4, seg_bot, outline="gray", fill="#e0e0e0")
                part = filled_height - y_top
                c.create_rectangle(4, seg_bot - part, w - 4, seg_bot, outline="gray", fill="#e6c229")

    def _build_control_section(self, parent: ttk.Frame) -> None:
        """Section Contrôle : label, bouton Automatique ou Manuelle, cadre manuel (Manuelle + 56 % + Ouvrir/Fermer)."""
        control_row = ttk.Frame(parent)
        control_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 4))
        ttk.Label(control_row, text="Contrôle :").grid(row=0, column=0, sticky="w", padx=(0, 8))

        self._auto_btn = ttk.Button(control_row, text="Automatique", command=self._on_auto_clicked)
        self._auto_btn.grid(row=0, column=1, padx=(0, 4))
        self._manual_btn = ttk.Button(control_row, text="Manuelle", command=self._on_manual_clicked)
        self._manual_btn.grid(row=0, column=2, padx=(0, 4))

        manual_box = ttk.LabelFrame(parent, text="")
        manual_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        manual_box.columnconfigure(1, weight=0)

        self._manual_btn_in_box = ttk.Button(manual_box, text="Manuelle", command=self._on_manual_clicked)
        self._manual_btn_in_box.grid(row=0, column=0, padx=(8, 8), pady=(6, 4))
        self._manual_entry = ttk.Entry(manual_box, width=6, textvariable=self._manual_percent_var)
        self._manual_entry.grid(row=0, column=1, padx=(0, 4), pady=(6, 4))
        ttk.Label(manual_box, text="%").grid(row=0, column=2, sticky="w", pady=(6, 4))
        self._open_button = ttk.Button(manual_box, text="Ouvrir la porte", command=self._on_open_clicked)
        self._open_button.grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 2))
        self._close_button = ttk.Button(manual_box, text="Fermer la porte", command=self._on_close_clicked)
        self._close_button.grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 6))

        self._manual_frame = manual_box

    def _build_bottom_section(self, parent: ttk.Frame) -> None:
        """Section basse : gauche Moteur/Direction, droite Détecteur/Vitesse."""
        bottom = ttk.Frame(parent)
        bottom.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=0)

        left = ttk.Frame(bottom)
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="Moteur :").grid(row=0, column=0, sticky="w")
        ttk.Label(left, textvariable=self._motor_state_var).grid(row=0, column=1, sticky="w", padx=(8, 16))
        ttk.Label(left, text="Direction :").grid(row=1, column=0, sticky="w")
        ttk.Label(left, textvariable=self._motor_direction_var).grid(row=1, column=1, sticky="w", padx=(8, 0))

        right = ttk.Frame(bottom)
        right.grid(row=0, column=1, sticky="w")
        ttk.Label(right, text="Détecteur de distance :").grid(row=0, column=0, sticky="w")
        ttk.Label(right, textvariable=self._distance_var).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(right, text="Vitesse :").grid(row=1, column=0, sticky="w")
        ttk.Label(right, textvariable=self._speed_var).grid(row=1, column=1, sticky="w", padx=(8, 0))

    def _apply_mode_to_ui(self) -> None:
        is_manual = self._mode_var.get() == "manual"
        state = "normal" if is_manual else "disabled"

        self._manual_entry.configure(state=state)
        self._open_button.configure(state=state)
        self._close_button.configure(state=state)

        # Bouton "sélectionné" = désactivé visuellement (Automatique enfoncé en auto, Manuelle en manuel)
        self._auto_btn.configure(state="disabled" if not is_manual else "normal")
        self._manual_btn.configure(state="disabled" if is_manual else "normal")
        self._manual_btn_in_box.configure(state="disabled" if is_manual else "normal")

        if hasattr(self, "_mode_display_var"):
            self._mode_display_var.set("Manuelle | Automatique")

    def _on_auto_clicked(self) -> None:
        self._mode_var.set("auto")
        self._controller.set_mode("auto")
        self._apply_mode_to_ui()

    def _on_manual_clicked(self) -> None:
        self._mode_var.set("manual")
        self._controller.set_mode("manual")
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

        self._draw_opening_bar(snapshot.current_opening_percent)

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

