from __future__ import annotations

import json
import logging
import os
import time
from decimal import Decimal
from typing import Any, Optional

from agents.database_agent import DatabaseAgent
from controller import SystemSnapshot
from schemas.telemetry_schema import OutgoingTelemetry

logger = logging.getLogger(__name__)

try:
    from azure.iot.device import IoTHubDeviceClient, Message  # type: ignore[import-untyped]
except Exception:
    IoTHubDeviceClient = None
    Message = None


class TelemetryAgent:
    """Persists telemetry every minute and syncs pending messages to IoT Hub."""

    def __init__(self, database_agent: DatabaseAgent) -> None:
        self._database_agent = database_agent
        self._device_id = os.getenv("DEVICE_ID", "porte_serre_01")
        self._interval_s = float(os.getenv("TELEMETRY_INTERVAL_SECONDS", "60"))
        self._last_send_ts = 0.0
        self._iot_client = self._build_iot_client()

    def _build_iot_client(self) -> Optional[Any]:
        conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING", "").strip()
        if not conn_str:
            logger.info("IoT Hub: variable IOTHUB_DEVICE_CONNECTION_STRING absente.")
            return None
        if IoTHubDeviceClient is None:
            logger.warning("azure-iot-device non installé: envoi IoT désactivé.")
            return None
        try:
            client = IoTHubDeviceClient.create_from_connection_string(conn_str)
            client.connect()
            logger.info("IoT Hub: connexion device établie.")
            return client
        except Exception as exc:
            logger.warning("IoT Hub: connexion impossible (%s).", exc)
            return None

    def maybe_send_telemetry(self, snapshot: SystemSnapshot, mode: str) -> None:
        now = time.monotonic()
        if now - self._last_send_ts < self._interval_s:
            return
        self._last_send_ts = now

        telemetry = OutgoingTelemetry.from_snapshot(snapshot=snapshot, mode=mode, device_id=self._device_id)
        payload = telemetry.to_payload()
        self._database_agent.insert_message_envoye(payload)
        self._try_send_and_mark(telemetry.to_iot_message())
        self._flush_pending_messages()

    def _try_send_and_mark(self, iot_payload: dict[str, object]) -> bool:
        if self._iot_client is None or Message is None:
            return False
        try:
            msg = Message(json.dumps(iot_payload))
            msg.content_encoding = "utf-8"
            msg.content_type = "application/json"
            self._iot_client.send_message(msg)
            self._database_agent.mark_message_envoye(str(iot_payload["id_message"]))
            return True
        except Exception as exc:
            logger.warning("IoT Hub send échoué (%s). Message conservé en attente.", exc)
            return False

    def _flush_pending_messages(self) -> None:
        pending = self._database_agent.fetch_pending_messages(limit=20)
        for row in pending:
            iot_payload = self._to_json_serializable_payload(dict(row))
            self._try_send_and_mark(iot_payload)

    def _to_json_serializable_payload(self, payload: dict[str, object]) -> dict[str, object]:
        serializable: dict[str, object] = {}
        for key, value in payload.items():
            if isinstance(value, Decimal):
                serializable[key] = float(value)
                continue
            if hasattr(value, "isoformat"):
                serializable[key] = value.isoformat()
                continue
            serializable[key] = value
        return serializable

