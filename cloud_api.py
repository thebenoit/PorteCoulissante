from __future__ import annotations

from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from agents.cloud_api_agent import CloudApiAgent
from schemas.cloud_api_schemas import (
    CommandAckRequest,
    CommandAckResponse,
    CommandPendingListResponse,
    CommandRequest,
    CommandResponse,
    DeviceTelemetryHistoryResponse,
    DeviceTelemetryResponse,
)

load_dotenv(override=True)

app = FastAPI(
    title="PorteCoulissante Cloud API",
    version="1.0.0",
    description="API minimale pour lire la telemetrie Cosmos DB et creer des commandes cloud.",
)

cloud_agent = CloudApiAgent()
COSMOS_NOT_CONFIGURED_DETAIL = (
    "Cosmos DB n'est pas configure (COSMOS_ENDPOINT/COSMOS_KEY manquants)."
)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "cosmos_ready": cloud_agent.is_ready}


@app.get(
    "/devices/{device_id}/latest",
    responses={503: {"description": "Cosmos DB non configure."}},
)
def get_device_latest(device_id: str) -> DeviceTelemetryResponse:
    if not cloud_agent.is_ready:
        raise HTTPException(
            status_code=503,
            detail=COSMOS_NOT_CONFIGURED_DETAIL,
        )
    return DeviceTelemetryResponse(item=cloud_agent.get_latest_telemetry(device_id=device_id))


@app.get(
    "/devices/{device_id}/history",
    responses={503: {"description": "Cosmos DB non configure."}},
)
def get_device_history(
    device_id: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> DeviceTelemetryHistoryResponse:
    if not cloud_agent.is_ready:
        raise HTTPException(
            status_code=503,
            detail=COSMOS_NOT_CONFIGURED_DETAIL,
        )
    return DeviceTelemetryHistoryResponse(
        items=cloud_agent.get_telemetry_history(device_id=device_id, limit=limit)
    )


@app.post("/devices/{device_id}/commands")
def create_device_command(device_id: str, payload: CommandRequest) -> CommandResponse:
    command = cloud_agent.create_command(
        device_id=device_id,
        mode=payload.mode,
        value=payload.valeur,
        action=payload.action,
    )
    return CommandResponse(accepted=True, command=command)


@app.get(
    "/devices/{device_id}/commands/pending",
    responses={503: {"description": "Cosmos DB non configure."}},
)
def get_pending_commands(
    device_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CommandPendingListResponse:
    if not cloud_agent.is_ready:
        raise HTTPException(
            status_code=503,
            detail=COSMOS_NOT_CONFIGURED_DETAIL,
        )
    return CommandPendingListResponse(
        items=cloud_agent.get_pending_commands(device_id=device_id, limit=limit)
    )


@app.post(
    "/devices/{device_id}/commands/{command_id}/ack",
    responses={404: {"description": "Commande introuvable."}, 503: {"description": "Cosmos DB non configure."}},
)
def ack_device_command(
    device_id: str,
    command_id: str,
    payload: CommandAckRequest,
) -> CommandAckResponse:
    if not cloud_agent.is_ready:
        raise HTTPException(
            status_code=503,
            detail=COSMOS_NOT_CONFIGURED_DETAIL,
        )
    updated = cloud_agent.ack_command(
        device_id=device_id,
        command_id=command_id,
        status=payload.status,
        message=payload.message,
        mode_applique=payload.mode_applique,
        valeur_appliquee=payload.valeur_appliquee,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Commande introuvable.")
    return CommandAckResponse(updated=True, command=updated)
