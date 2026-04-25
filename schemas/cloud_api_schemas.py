from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class CommandRequest(BaseModel):
    mode: Literal["automatique", "manuelle"] = Field(
        description="Mode cible pour la porte."
    )
    valeur: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Valeur d'ouverture (%) en mode manuelle.",
    )
    action: Literal["ouvrir", "fermer"] | None = Field(
        default=None,
        description="Action rapide facultative.",
    )

    @model_validator(mode="after")
    def validate_command_payload(self) -> "CommandRequest":
        if self.mode == "manuelle" and self.action is None and self.valeur is None:
            raise ValueError("Une commande manuelle doit inclure 'valeur' ou 'action'.")
        if self.mode == "automatique" and self.valeur is not None:
            raise ValueError("La valeur (%) ne doit pas etre fournie en mode automatique.")
        return self


class CommandResponse(BaseModel):
    accepted: bool
    command: dict[str, Any]


class CommandPendingListResponse(BaseModel):
    items: list[dict[str, Any]]


class CommandAckRequest(BaseModel):
    status: Literal["accomplit", "probleme"] = Field(
        description="Etat final de la commande traitee par l'objet."
    )
    message: str | None = Field(
        default=None,
        description="Detail optionnel (erreur, confirmation, etc.).",
    )
    mode_applique: Literal["automatique", "manuelle"] | None = Field(
        default=None,
        description="Mode effectivement applique sur l'objet.",
    )
    valeur_appliquee: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Valeur d'ouverture effectivement appliquee (si pertinent).",
    )


class CommandAckResponse(BaseModel):
    updated: bool
    command: dict[str, Any] | None


class DeviceTelemetryResponse(BaseModel):
    item: dict[str, Any] | None


class DeviceTelemetryHistoryResponse(BaseModel):
    items: list[dict[str, Any]]
