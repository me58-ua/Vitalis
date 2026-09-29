from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrescriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_id: UUID
    patient_id: UUID
    professional_id: UUID
    file_url: str
    notas: str | None
    created_at: datetime


class PrescriptionListResponse(BaseModel):
    prescriptions: list[PrescriptionResponse]
    total: int
    page: int
    page_size: int
    message: str | None = None


class PrescriptionAuthorizationCreate(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class PrescriptionAuthorizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_id: UUID
    authorized_by: UUID
    reason: str | None
    authorized_at: datetime