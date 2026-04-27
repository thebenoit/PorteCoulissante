"""
Entrée alternative sans interface Tkinter.

Cette version pilote le système en mode console:
- boucle de contrôle périodique;
- commandes clavier (auto/manual/open/close/set <0-100>/status/quit);
- télémétrie et feedback de commandes cloud conservés.
"""

from __future__ import annotations

from dotenv import load_dotenv

# .env prime sur des exports shell erronés (ex. DB_PORT=6000).
load_dotenv(override=True)

import logging
import queue
import threading
import time

from agents.command_feedback_agent import CommandFeedbackAgent
from agents.database_agent import DatabaseAgent
from agents.telemetry_agent import TelemetryAgent
from algorithm import clamp
from controller import GreenhouseController, SystemSnapshot
from motor import create_motor
from sensors import SensorManager

CONTROL_LOOP_INTERVAL_SECONDS = 1.0


class ConsoleGreenhouseApp:
    """Application console qui remplace l'UI Tkinter."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._database_agent = DatabaseAgent()
        self._telemetry_agent = TelemetryAgent(database_agent=self._database_agent)
        self._sensor_manager = SensorManager()
        self._motor = create_motor(initial_opening_percent=0.0)
        self._controller = GreenhouseController(
            sensor_manager=self._sensor_manager,
            motor=self._motor,
            database_agent=self._database_agent,
        )
        self._command_feedback_agent = CommandFeedbackAgent(controller=self._controller)
        self._command_queue: queue.Queue[str] = queue.Queue()
        self._should_stop = False

    def run(self) -> None:
        self._print_welcome()
        self._start_input_thread()
        try:
            while not self._should_stop:
                self._process_pending_commands()
                self._execute_control_loop_iteration()
                time.sleep(CONTROL_LOOP_INTERVAL_SECONDS)
        finally:
            self._sensor_manager.close()

    def _print_welcome(self) -> None:
        print("Controle serre - mode console (sans Tkinter).")
        print("Commandes: auto | manual | open | close | set <0-100> | status | help | quit")

    def _start_input_thread(self) -> None:
        thread = threading.Thread(target=self._input_loop, name="console-input", daemon=True)
        thread.start()

    def _input_loop(self) -> None:
        while not self._should_stop:
            try:
                raw = input("> ").strip()
            except EOFError:
                self._should_stop = True
                break
            if raw:
                self._command_queue.put(raw)

    def _process_pending_commands(self) -> None:
        while not self._command_queue.empty():
            command = self._command_queue.get_nowait()
            self._apply_console_command(command)

    def _apply_console_command(self, raw_command: str) -> None:
        parts = raw_command.split()
        command = parts[0].lower()
        if command == "help":
            self._print_welcome()
            return
        if command == "quit":
            self._should_stop = True
            print("Arret de l'application.")
            return
        if command == "auto":
            self._controller.set_mode("auto")
            print("Mode automatique active.")
            return
        if command == "manual":
            self._controller.set_mode("manual")
            print("Mode manuel active.")
            return
        if command == "open":
            self._controller.set_mode("manual")
            self._controller.set_target_fully_open()
            print("Commande: ouvrir completement.")
            return
        if command == "close":
            self._controller.set_mode("manual")
            self._controller.set_target_fully_closed()
            print("Commande: fermer completement.")
            return
        if command == "set":
            self._apply_manual_set_command(parts)
            return
        if command == "status":
            self._print_last_snapshot_or_hint()
            return
        print("Commande inconnue. Tapez 'help' pour la liste.")

    def _apply_manual_set_command(self, parts: list[str]) -> None:
        if len(parts) != 2:
            print("Usage: set <0-100>")
            return
        try:
            value = float(parts[1].replace(",", "."))
        except ValueError:
            print("Valeur invalide, nombre attendu.")
            return
        safe_value = clamp(value, 0.0, 100.0)
        self._controller.set_mode("manual")
        self._controller.set_manual_target_opening_percent(safe_value)
        print(f"Consigne manuelle fixee a {safe_value:.1f}%.")

    def _print_last_snapshot_or_hint(self) -> None:
        snapshot = self._controller.get_last_snapshot()
        if snapshot is None:
            print("Aucun snapshot encore disponible.")
            return
        self._print_snapshot(snapshot)

    def _execute_control_loop_iteration(self) -> None:
        try:
            snapshot = self._controller.step_once(dt_seconds=CONTROL_LOOP_INTERVAL_SECONDS)
            self._command_feedback_agent.maybe_process_pending_commands()
            self._telemetry_agent.maybe_send_telemetry(snapshot=snapshot, mode=self._controller.get_mode())
            self._print_snapshot(snapshot)
        except Exception as exc:
            self._logger.exception("Iteration console en echec: %s", exc)

    def _print_snapshot(self, snapshot: SystemSnapshot) -> None:
        warnings = " | ".join(snapshot.warnings) if snapshot.warnings else "aucun"
        motor = snapshot.motor_status
        print(
            "[mode=%s] T=%.1fC L=%.0f%% auto=%.1f%% target=%.1f%% current=%.1f%% "
            "distance=%.1fcm motor=%s dir=%s rpm=%d warnings=%s"
            % (
                self._controller.get_mode(),
                snapshot.readings.temperature_c,
                snapshot.readings.luminosity_percent,
                snapshot.automatic_opening_percent,
                snapshot.target_opening_percent,
                snapshot.current_opening_percent,
                snapshot.distance_cm,
                "on" if motor.is_running else "off",
                motor.direction_label or "--",
                motor.speed_rpm,
                warnings,
            )
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    ConsoleGreenhouseApp().run()


if __name__ == "__main__":
    main()
