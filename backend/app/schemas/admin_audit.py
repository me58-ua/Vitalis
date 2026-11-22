from datetime import datetime, timezone
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import AuditAction, UserRole


class AuditFilters(BaseModel):
    actor_id: UUID | None = None
    actor_role: UserRole | None = None
    accion: AuditAction | None = None
    entidad: str | None = Field(default=None, min_length=1, max_length=80)
    entidad_id: UUID | None = None
    patient_id: UUID | None = Field(default=None, description="Patient user account UUID (users.id)")
    from_date: AwareDatetime | None = None
    to_date: AwareDatetime | None = None

    @field_validator("from_date", "to_date")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before or equal to to_date")
        return self


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    actor_role: UserRole | None
    patient_id: UUID | None = Field(description="Patient user account UUID (users.id)")
    accion: AuditAction
    entidad: str
    entidad_id: UUID | None
    fecha_hora: datetime

    @field_validator("fecha_hora")
    @classmethod
    def utc_date(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AuditListQuery(AuditFilters):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
