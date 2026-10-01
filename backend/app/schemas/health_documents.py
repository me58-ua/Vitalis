from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.health_document import HealthDocumentType


class HealthDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    tipo: HealthDocumentType
    file_url: str
    descripcion: str | None
    fecha_subida: datetime


class HealthDocumentListResponse(BaseModel):
    documents: list[HealthDocumentResponse]
    total: int


class HealthDocumentDescription(BaseModel):
    descripcion: str | None = Field(default=None, max_length=2000)