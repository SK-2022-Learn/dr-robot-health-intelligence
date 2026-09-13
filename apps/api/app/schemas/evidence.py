"""Evidence-link contracts requiring at least one trusted target."""

from datetime import datetime

from pydantic import model_validator

from app.schemas.common import SchemaModel


class EvidenceLinkCreate(SchemaModel):
    health_event_id: str | None = None
    observation_id: str | None = None
    medication_id: str | None = None
    symptom_id: str | None = None
    source_document_id: str
    page_number: int | None = None
    source_excerpt: str | None = None

    @model_validator(mode="after")
    def require_target(self) -> "EvidenceLinkCreate":
        if not any(
            (
                self.health_event_id,
                self.observation_id,
                self.medication_id,
                self.symptom_id,
            )
        ):
            raise ValueError("An evidence link must target an event or observation.")
        return self


class EvidenceLinkRead(EvidenceLinkCreate):
    id: str
    created_at: datetime
