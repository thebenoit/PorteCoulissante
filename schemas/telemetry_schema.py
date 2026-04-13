from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from controller import SystemSnapshot


@dataclass(frozen=True)
class OutgoingTelemetry:
    id_message: str
    id_objet: str
    id_date: datetime
    status: str
    temperature: float
    luminosite: float
    ouverture_automatique: float
    mode: str
    ouverture_reelle: float
    erreur: str
    avertissement: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            "id_message": self.id_message,
            "id_objet": self.id_objet,
            "id_date": self.id_date.replace(tzinfo=None),
            "status": self.status,
            "temperature": self.temperature,
            "luminosite": self.luminosite,
            "ouverture_automatique": self.ouverture_automatique,
            "mode": self.mode,
            "ouverture_reelle": self.ouverture_reelle,
            "erreur": self.erreur,
            "avertissement": self.avertissement,
        }

    def to_iot_message(self) -> dict[str, object]:
        return {
            "id_message": self.id_message,
            "id_objet": self.id_objet,
            "id_date": self.id_date.isoformat(),
            "status": self.status,
            "temperature": self.temperature,
            "luminosite": self.luminosite,
            "ouverture_automatique": self.ouverture_automatique,
            "mode": self.mode,
            "ouverture_reelle": self.ouverture_reelle,
            "erreur": self.erreur,
            "avertissement": self.avertissement,
        }

    @classmethod
    def from_snapshot(cls, snapshot: SystemSnapshot, mode: str, device_id: str) -> "OutgoingTelemetry":
        warnings_text = " | ".join(snapshot.warnings) if snapshot.warnings else None
        return cls(
            id_message=str(uuid4()),
            id_objet=device_id,
            id_date=datetime.now(timezone.utc),
            status="en_attente",
            temperature=float(snapshot.readings.temperature_c),
            luminosite=float(snapshot.readings.luminosity_percent),
            ouverture_automatique=float(snapshot.automatic_opening_percent),
            mode="manuelle" if mode == "manual" else "automatique",
            ouverture_reelle=float(snapshot.current_opening_percent),
            erreur="oui" if snapshot.warnings else "non",
            avertissement=warnings_text,
        )

