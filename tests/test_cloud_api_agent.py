from __future__ import annotations

from unittest.mock import MagicMock

from agents.cloud_api_agent import CloudApiAgent, CosmosConfig


def test_get_pending_commands_sorts_by_id_date_in_memory() -> None:
    agent = object.__new__(CloudApiAgent)
    agent._config = CosmosConfig(
        endpoint="https://example.local",
        key="key",
        database_name="db",
        telemetry_container_name="telemetry",
        command_container_name="commands",
    )
    mock_container = MagicMock()
    mock_container.query_items.return_value = [
        {"id": "b", "id_date": "2026-04-02T00:00:00Z"},
        {"id": "a", "id_date": "2026-04-01T00:00:00Z"},
    ]
    agent._command_container = mock_container

    items = CloudApiAgent.get_pending_commands(agent, device_id="porte_serre_01", limit=10)

    assert [item["id"] for item in items] == ["a", "b"]
    mock_container.query_items.assert_called_once()
