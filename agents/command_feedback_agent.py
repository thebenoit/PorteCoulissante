from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
from urllib import error, parse, request

from controller import GreenhouseController

logger = logging.getLogger(__name__)


class CommandFeedbackAgent:
    """Poll cloud pending commands, apply them locally, and ACK execution status."""

    def __init__(self, controller: GreenhouseController) -> None:
        self._controller = controller
        self._enabled = os.getenv("COMMAND_FEEDBACK_ENABLED", "1") == "1"
        self._base_url = os.getenv("CLOUD_API_BASE_URL", "").strip().rstrip("/")
        self._device_id = os.getenv("DEVICE_ID", "porte_serre_01")
        self._poll_interval_s = float(os.getenv("COMMAND_POLL_INTERVAL_SECONDS", "3"))
        self._last_poll_ts = 0.0
        self._logged_disabled_reason = False

    def maybe_process_pending_commands(self) -> None:
        if not self._enabled:
            return
        if not self._base_url:
            if not self._logged_disabled_reason:
                logger.info(
                    "Command feedback desactive: CLOUD_API_BASE_URL absent."
                )
                self._logged_disabled_reason = True
            return

        now = time.monotonic()
        if now - self._last_poll_ts < self._poll_interval_s:
            return
        self._last_poll_ts = now

        pending_items = self._fetch_pending_commands(limit=5)
        for item in pending_items:
            command_id = str(item.get("id", "")).strip()
            if not command_id:
                continue
            status, message, applied_mode, applied_value = self._apply_command(item)
            self._send_ack(
                command_id=command_id,
                status=status,
                message=message,
                mode_applique=applied_mode,
                valeur_appliquee=applied_value,
            )

    def _fetch_pending_commands(self, limit: int) -> list[dict[str, Any]]:
        query = parse.urlencode({"limit": str(limit)})
        url = (
            f"{self._base_url}/devices/"
            f"{parse.quote(self._device_id, safe='')}/commands/pending?{query}"
        )
        try:
            req = request.Request(url=url, method="GET")
            with request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
            return []
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Impossible de recuperer les commandes en attente: %s", exc)
            return []

    def _apply_command(
        self, command: dict[str, Any]
    ) -> tuple[str, str | None, str | None, float | None]:
        mode = str(command.get("commande", "")).strip().lower()
        action = command.get("action")
        value = command.get("valeur")
        try:
            if mode == "automatique":
                self._controller.set_mode("auto")
                return "accomplit", "Mode automatique applique.", "automatique", None

            if mode != "manuelle":
                return "probleme", f"Mode de commande invalide: {mode}", None, None

            self._controller.set_mode("manual")
            if action == "ouvrir":
                self._controller.set_target_fully_open()
                return "accomplit", "Commande ouvrir appliquee.", "manuelle", 100.0
            if action == "fermer":
                self._controller.set_target_fully_closed()
                return "accomplit", "Commande fermer appliquee.", "manuelle", 0.0

            if value is None:
                return (
                    "probleme",
                    "Commande manuelle sans valeur ni action.",
                    "manuelle",
                    None,
                )
            manual_value = float(value)
            if manual_value < 0 or manual_value > 100:
                return (
                    "probleme",
                    "Valeur manuelle hors plage (0-100).",
                    "manuelle",
                    None,
                )
            self._controller.set_manual_target_opening_percent(manual_value)
            return (
                "accomplit",
                f"Commande manuelle appliquee a {manual_value:.1f}%.",
                "manuelle",
                manual_value,
            )
        except Exception as exc:
            return "probleme", f"Echec application commande: {exc}", None, None

    def _send_ack(
        self,
        command_id: str,
        status: str,
        message: str | None,
        mode_applique: str | None,
        valeur_appliquee: float | None,
    ) -> None:
        url = (
            f"{self._base_url}/devices/"
            f"{parse.quote(self._device_id, safe='')}/commands/"
            f"{parse.quote(command_id, safe='')}/ack"
        )
        payload = {
            "status": status,
            "message": message,
            "mode_applique": mode_applique,
            "valeur_appliquee": valeur_appliquee,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=url,
            method="POST",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=5) as resp:
                _ = resp.read()
        except (error.URLError, TimeoutError) as exc:
            logger.warning("Impossible d'envoyer le feedback de commande %s: %s", command_id, exc)
