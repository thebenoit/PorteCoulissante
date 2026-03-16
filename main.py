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
from motor import MotorSimulator, create_motor
from sensors import SensorManager


class GreenhouseApp(tk.Tk):
    """Interface Tkinter (UI) : affiche l'état et relaie les actions utilisateur vers le contrôleur."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Contrôle d'une porte d'aération d'une serre")
        self.minsize(560, 320)

        self._logger = logging.getLogger(__name__)

        self._sensor_manager = SensorManager()
        self._motor = create_motor(initial_opening_percent=0.0)
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

        border_frame = tk.Frame(self, bg="#1e3a5f", padx=2, pady=2)
        border_frame.grid(row=0, column=0, sticky="nsew")
        border_frame.columnconfigure(0, weight=1)

        main_frame = ttk.Frame(border_frame, padding=12)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0)

        # Titre centré
        title = ttk.Label(
            main_frame,
            text="Contrôle d'une porte d'aération d'une serre",
            font=("TkDefaultFont", 14, "bold"),
        )
        title.grid(row=0, column=0, columnspan=2, pady=(0, 8))

        # ----- Colonne gauche (row 1) : Température, Luminosité, Ouverture auto -----
        self._build_left_column(main_frame)
        # ----- Colonne droite (row 1) : Mode Manuelle | Automatique, barre, Ouverture % -----
        self._build_right_column(main_frame)

        # ----- Contrôle + cadre Manuelle (col 0) -----
        self._build_control_section(main_frame)

        # ----- Bas : Moteur/Direction (gauche) | Détecteur/Vitesse (droite) -----
        self._build_bottom_section(main_frame)

        self._manual_entry.bind("<Return>", lambda _event: self._on_apply_manual_opening_clicked())

        # Zone avertissements (visible dès qu'il y a des messages)
        self._warnings_var = tk.StringVar(value="")
        self._warnings_frame = ttk.LabelFrame(main_frame, text="Avertissements / Erreurs")
        self._warnings_label = ttk.Label(
            self._warnings_frame,
            textvariable=self._warnings_var,
            wraplength=500,
        )
        self._warnings_label.grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self._warnings_frame.grid(row=5, column=0, columnspan=2, padx=0, pady=6, sticky="ew")
        self._warnings_frame.grid_remove()

        footer = ttk.Label(
            main_frame,
            text="Simulation PC" if not self._sensor_manager.is_hardware_available else "Raspberry Pi détecté",
        )
        footer.grid(row=6, column=0, columnspan=2, pady=(0, 0), sticky="w")

    def _build_left_column(self, parent: ttk.Frame) -> None:
        """Colonne gauche : température, luminosité, ouverture automatique."""
        left = ttk.Frame(parent)
        left.grid(row=1, column=0, sticky="nw", pady=(0, 8))
        ttk.Label(left, text="Température interne ambiante :").grid(row=0, column=0, sticky="w")
        ttk.Label(left, textvariable=self._temperature_var).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(left, text="Intensité lumineuse à l'interne :").grid(row=1, column=0, sticky="w")
        ttk.Label(left, textvariable=self._luminosity_var).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Label(left, text="Ouverture de la porte automatique :").grid(row=2, column=0, sticky="w")
        ttk.Label(left, textvariable=self._automatic_opening_var).grid(row=2, column=1, sticky="w", padx=(8, 0))

    def _build_right_column(self, parent: ttk.Frame) -> None:
        """Colonne droite : Mode Manuelle | Automatique (avec terme actif mis en évidence), barre, Ouverture %."""
        right = ttk.Frame(parent)
        right.grid(row=1, column=1, sticky="nw", padx=(24, 0), pady=(0, 8))

        ttk.Label(right, text="Mode :").grid(row=0, column=0, sticky="w")
        mode_frame = ttk.Frame(right)
        mode_frame.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self._mode_manual_label = ttk.Label(mode_frame, text="Manuelle")
        self._mode_manual_label.grid(row=0, column=0, sticky="w")
        ttk.Label(mode_frame, text=" | ").grid(row=0, column=1, sticky="w")
        self._mode_auto_label = ttk.Label(mode_frame, text="Automatique")
        self._mode_auto_label.grid(row=0, column=2, sticky="w")

        self._opening_canvas = tk.Canvas(
            right, width=32, height=72, bg="white", highlightthickness=1, highlightbackground="gray"
        )
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
        """Section Contrôle (col 0) : label, bouton Automatique, Manuelle ; cadre manuel avec Ouvrir/Fermer côte à côte."""
        control_row = ttk.Frame(parent)
        control_row.grid(row=2, column=0, sticky="w", pady=(4, 4))
        ttk.Label(control_row, text="Contrôle :").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._auto_btn = ttk.Button(control_row, text="Automatique", command=self._on_auto_clicked)
        self._auto_btn.grid(row=0, column=1, padx=(0, 4))
        self._manual_btn = ttk.Button(control_row, text="Manuelle", command=self._on_manual_clicked)
        self._manual_btn.grid(row=0, column=2, padx=(0, 4))

        manual_box = ttk.LabelFrame(parent, text="")
        manual_box.grid(row=3, column=0, sticky="ew", pady=(2, 8))
        manual_box.columnconfigure(1, weight=0)

        self._manual_btn_in_box = ttk.Button(manual_box, text="Manuelle", command=self._on_manual_clicked)
        self._manual_btn_in_box.grid(row=0, column=0, padx=(8, 8), pady=(6, 4))
        self._manual_entry = ttk.Entry(manual_box, width=6, textvariable=self._manual_percent_var)
        self._manual_entry.grid(row=0, column=1, padx=(0, 4), pady=(6, 4))
        ttk.Label(manual_box, text="%").grid(row=0, column=2, sticky="w", pady=(6, 4))
        btn_row = ttk.Frame(manual_box)
        btn_row.grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))
        self._open_button = ttk.Button(btn_row, text="Ouvrir la porte", command=self._on_open_clicked)
        self._open_button.grid(row=0, column=0, padx=(0, 8))
        self._close_button = ttk.Button(btn_row, text="Fermer la porte", command=self._on_close_clicked)
        self._close_button.grid(row=0, column=1, padx=0)

        self._manual_frame = manual_box

    def _build_bottom_section(self, parent: ttk.Frame) -> None:
        """Section basse : gauche Moteur (En marche | En arrêt), Direction (Gauche | Droite) ; droite Détecteur, Vitesse."""
        bottom = ttk.Frame(parent)
        bottom.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=0)

        left = ttk.Frame(bottom)
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="Moteur :").grid(row=0, column=0, sticky="w")
        motor_frame = ttk.Frame(left)
        motor_frame.grid(row=0, column=1, sticky="w", padx=(8, 16))
        self._motor_run_label = ttk.Label(motor_frame, text="En marche")
        self._motor_run_label.grid(row=0, column=0, sticky="w")
        ttk.Label(motor_frame, text=" | ").grid(row=0, column=1, sticky="w")
        self._motor_stop_label = ttk.Label(motor_frame, text="En arrêt")
        self._motor_stop_label.grid(row=0, column=2, sticky="w")
        ttk.Label(left, text="Direction :").grid(row=1, column=0, sticky="w")
        dir_frame = ttk.Frame(left)
        dir_frame.grid(row=1, column=1, sticky="w", padx=(8, 0))
        self._dir_left_label = ttk.Label(dir_frame, text="Gauche")
        self._dir_left_label.grid(row=0, column=0, sticky="w")
        ttk.Label(dir_frame, text=" | ").grid(row=0, column=1, sticky="w")
        self._dir_right_label = ttk.Label(dir_frame, text="Droite")
        self._dir_right_label.grid(row=0, column=2, sticky="w")

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

        self._auto_btn.configure(state="disabled" if not is_manual else "normal")
        self._manual_btn.configure(state="disabled" if is_manual else "normal")
        self._manual_btn_in_box.configure(state="disabled" if is_manual else "normal")

        self._update_mode_highlight(is_manual)

    def _update_mode_highlight(self, is_manual: bool) -> None:
        """Met en évidence le mode actif (Manuelle ou Automatique) en gras."""
        bold = ("TkDefaultFont", 9, "bold")
        normal = ("TkDefaultFont", 9)
        self._mode_manual_label.configure(font=bold if is_manual else normal)
        self._mode_auto_label.configure(font=bold if not is_manual else normal)

    def _update_motor_direction_highlight(self, is_running: bool, direction_label: str) -> None:
        """Met en évidence Moteur (En marche / En arrêt) et Direction (Gauche / Droite)."""
        bold = ("TkDefaultFont", 9, "bold")
        normal = ("TkDefaultFont", 9)
        self._motor_run_label.configure(font=bold if is_running else normal)
        self._motor_stop_label.configure(font=bold if not is_running else normal)
        is_left = direction_label == "Gauche"
        self._dir_left_label.configure(font=bold if is_left else normal)
        self._dir_right_label.configure(font=bold if not is_left else normal)

    def _on_auto_clicked(self) -> None:
        self._logger.info("Bouton cliqué: passage en mode automatique.")
        self._mode_var.set("auto")
        self._controller.set_mode("auto")
        self._apply_mode_to_ui()

    def _on_manual_clicked(self) -> None:
        self._logger.info("Bouton cliqué: passage en mode manuel.")
        self._mode_var.set("manual")
        self._controller.set_mode("manual")
        self._apply_mode_to_ui()

    def _on_apply_manual_opening_clicked(self) -> None:
        self._logger.info(
            "Bouton cliqué: appliquer ouverture manuelle demandée (champ texte='%s').",
            self._manual_percent_var.get(),
        )
        value = self._parse_manual_opening_percent_or_none()
        if value is None:
            self._logger.warning("Ouverture manuelle invalide ou vide — aucune action lancée.")
            self.bell()
            return
        self._logger.info("Action: consigne ouverture manuelle fixée à %.1f%%.", value)
        self._controller.set_manual_target_opening_percent(value)

    def _on_open_clicked(self) -> None:
        self._logger.info("Bouton cliqué: ouvrir complètement la porte (cible 100%%).")
        self._controller.set_target_fully_open()
        self._manual_percent_var.set("100")

    def _on_close_clicked(self) -> None:
        self._logger.info("Bouton cliqué: fermer complètement la porte (cible 0%%).")
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
        clamped_dt = clamp(dt, 0.2, 1.2)
        self._logger.debug("Tick UI: dt=%.3f s (clampé à %.3f s) — mise à jour du contrôleur.", dt, clamped_dt)
        snapshot = self._controller.step_once(dt_seconds=clamped_dt)
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
        self._update_motor_direction_highlight(motor.is_running, motor.direction_label)
        self._speed_var.set(f"{motor.speed_rpm} tour/min")

        distance_text = "-- cm" if any("Détecteur de distance" in w for w in snapshot.warnings) else f"{snapshot.distance_cm:.0f} cm"
        self._distance_var.set(distance_text)
        self._opening_var.set(f"{snapshot.current_opening_percent:.0f} %")

        self._draw_opening_bar(snapshot.current_opening_percent)
        self._update_mode_highlight(self._mode_var.get() == "manual")

        if snapshot.warnings:
            self._warnings_var.set("\n".join(snapshot.warnings))
            self._warnings_frame.grid(row=5, column=0, columnspan=2, padx=0, pady=6, sticky="ew")
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

