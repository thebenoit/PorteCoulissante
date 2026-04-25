from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

try:
    from azure.cosmos import CosmosClient
except Exception:
    CosmosClient = None  # type: ignore[assignment]


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

QUERY_PARAM_DEVICE_ID = "@device_id"


@dataclass(frozen=True)
class CosmosConfig:
    endpoint: str
    key: str
    database_name: str
    telemetry_container_name: str
    command_container_name: str

    @classmethod
    def from_env(cls) -> "CosmosConfig":
        return cls(
            endpoint=os.getenv("COSMOS_ENDPOINT", "").strip(),
            key=os.getenv("COSMOS_KEY", "").strip(),
            database_name=os.getenv("COSMOS_DB_NAME", "db_objet_cloud").strip(),
            telemetry_container_name=os.getenv("COSMOS_TELEMETRY_CONTAINER", "telemetry").strip(),
            command_container_name=os.getenv("COSMOS_COMMAND_CONTAINER", "commands").strip(),
        )


class CloudApiAgent:
    """Reads telemetry from Cosmos DB and stores cloud commands."""

    def __init__(self, config: CosmosConfig | None = None) -> None:
        self._config = config or CosmosConfig.from_env()
        self._client = self._build_client()
        self._database = self._build_database()
        self._telemetry_container = self._build_container(self._config.telemetry_container_name)
        self._command_container = self._build_container(self._config.command_container_name)

    @property
    def is_ready(self) -> bool:
        return self._telemetry_container is not None

    def _build_client(self) -> Any | None:
        if CosmosClient is None:
            return None
        if not self._config.endpoint or not self._config.key:
            return None
        return CosmosClient(self._config.endpoint, credential=self._config.key)

    def _build_database(self) -> Any | None:
        if self._client is None:
            return None
        return self._client.get_database_client(self._config.database_name)

    def _build_container(self, container_name: str) -> Any | None:
        if self._database is None:
            return None
        try:
            return self._database.get_container_client(container_name)
        except Exception:
            return None

    def get_latest_telemetry(self, device_id: str) -> dict[str, Any] | None:
        if self._telemetry_container is None:
            return None
        query = (
            "SELECT TOP 1 c.id, c._ts, c.body, c.systemProperties "
            "FROM c "
            "WHERE IS_DEFINED(c.body.id_objet) AND c.body.id_objet = @device_id "
            "ORDER BY c._ts DESC"
        )
        params = [{"name": QUERY_PARAM_DEVICE_ID, "value": device_id}]
        items = list(
            self._telemetry_container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
        if not items:
            return None
        return dict(items[0])

    def get_telemetry_history(self, device_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self._telemetry_container is None:
            return []
        safe_limit = max(1, min(int(limit), 500))
        query = (
            "SELECT TOP @limit c.id, c._ts, c.body, c.systemProperties "
            "FROM c "
            "WHERE IS_DEFINED(c.body.id_objet) AND c.body.id_objet = @device_id "
            "ORDER BY c._ts DESC"
        )
        params = [
            {"name": QUERY_PARAM_DEVICE_ID, "value": device_id},
            {"name": "@limit", "value": safe_limit},
        ]
        return [
            dict(item)
            for item in self._telemetry_container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        ]

    def create_command(
        self,
        device_id: str,
        mode: str,
        value: float | None,
        action: str | None = None,
    ) -> dict[str, Any]:
        command = {
            "id": str(uuid4()),
            "id_objet": device_id,
            "type": "command",
            "id_date": _utc_iso_now(),
            "status": "en_attente",
            "commande": mode,
            "valeur": value,
            "action": action,
        }
        if self._command_container is not None:
            try:
                self._command_container.upsert_item(command)
            except Exception:
                # Le conteneur commands peut ne pas encore exister; on retourne quand meme
                # la commande pour permettre un premier test de l'API.
                pass
        return command

    def get_pending_commands(self, device_id: str, limit: int = 20) -> list[dict[str, Any]]:
        if self._command_container is None:
            return []
        safe_limit = max(1, min(int(limit), 100))
        query = (
            "SELECT TOP @limit c.id, c.id_objet, c.type, c.id_date, c.status, c.commande, c.valeur, c.action "
            "FROM c "
            "WHERE c.type = 'command' AND c.id_objet = @device_id AND c.status = 'en_attente' "
            "ORDER BY c.id_date ASC"
        )
        params = [
            {"name": QUERY_PARAM_DEVICE_ID, "value": device_id},
            {"name": "@limit", "value": safe_limit},
        ]
        return [
            dict(item)
            for item in self._command_container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        ]

    def ack_command(
        self,
        device_id: str,
        command_id: str,
        status: str,
        message: str | None = None,
        mode_applique: str | None = None,
        valeur_appliquee: float | None = None,
    ) -> dict[str, Any] | None:
        if self._command_container is None:
            return None
        query = (
            "SELECT TOP 1 c.id, c.id_objet, c.type, c.id_date, c.status, c.commande, c.valeur, c.action "
            "FROM c "
            "WHERE c.id = @command_id AND c.id_objet = @device_id"
        )
        params = [
            {"name": "@command_id", "value": command_id},
            {"name": QUERY_PARAM_DEVICE_ID, "value": device_id},
        ]
        items = list(
            self._command_container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            )
        )
        if not items:
            return None
        command = dict(items[0])
        command["status"] = status
        command["id_date_traitement"] = _utc_iso_now()
        command["message_traitement"] = message
        command["mode_applique"] = mode_applique
        command["valeur_appliquee"] = valeur_appliquee
        self._command_container.upsert_item(command)
        return command
