from __future__ import annotations

from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from agents.cloud_api_agent import CloudApiAgent
from schemas.cloud_api_schemas import (
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
            detail="Cosmos DB n'est pas configure (COSMOS_ENDPOINT/COSMOS_KEY manquants).",
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
            detail="Cosmos DB n'est pas configure (COSMOS_ENDPOINT/COSMOS_KEY manquants).",
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
