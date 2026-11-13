from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


PrescriptionType = Literal["medicacion", "prueba", "otro"]


class PrescriptionMetadata(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: PrescriptionType
    titulo: str = Field(min_length=1, max_length=300)
    fecha_emision: date
    fecha_caducidad: date | None = None
    codigo: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.fecha_caducidad is not None and self.fecha_caducidad < self.fecha_emision:
            raise ValueError("La fecha de caducidad no puede ser anterior a la fecha de emisión")
        self.codigo = self.codigo or None
        return self


class PrescriptionMetadataResponse(BaseModel):
    # Existing uploads retain unknown metadata rather than fabricated issue/expiry dates.
    tipo: PrescriptionType | None = None
    titulo: str | None = None
    fecha_emision: date | None = None
    fecha_caducidad: date | None = None
    codigo: str | None = None


class PrescriptionResponse(PrescriptionMetadataResponse):
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


class PatientPrescriptionResponse(PrescriptionMetadataResponse):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_id: UUID
    patient_id: UUID
    professional_id: UUID
    professional_name: str
    appointment_date: datetime
    appointment_reason: str | None = None
    file_url: str
    download_url: str
    notas: str | None
    created_at: datetime


class PatientPrescriptionListResponse(BaseModel):
    prescriptions: list[PatientPrescriptionResponse]
    total: int


class PrescriptionAuthorizationCreate(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class PrescriptionAuthorizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_id: UUID
    authorized_by: UUID
    reason: str | None
    authorized_at: datetime
