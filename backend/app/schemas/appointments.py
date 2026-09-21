from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AppointmentStatus, AppointmentType


class AdminScheduleCreate(BaseModel):
    professional_id: UUID
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    slot_duration_min: int = Field(gt=0)
    is_active: bool

    @model_validator(mode="after")
    def validate_time_range(self) -> "AdminScheduleCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AdminScheduleResponse(AdminScheduleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class ProfessionalScheduleResponse(AdminScheduleResponse):
    pass


class AdminAppointmentCreate(BaseModel):
    patient_id: UUID
    professional_id: UUID
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    reason: str | None = None

    @model_validator(mode="after")
    def validate_appointment(self) -> "AdminAppointmentCreate":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AdminAppointmentResponse(AdminAppointmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: AppointmentStatus
    room_id: UUID
    created_at: datetime
    updated_at: datetime


class AdminAppointmentUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: AppointmentStatus | None = None
    type: AppointmentType | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "AdminAppointmentUpdate":
        if self.start_time is not None and self.start_time.tzinfo is None:
            raise ValueError("start_time must include a timezone")
        if self.end_time is not None and self.end_time.tzinfo is None:
            raise ValueError("end_time must include a timezone")
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        return self


class ProfessionalAppointmentCreate(BaseModel):
    patient_id: UUID
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    reason: str | None = None

    @model_validator(mode="after")
    def validate_appointment(self) -> "ProfessionalAppointmentCreate":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ConsultationNoteCreate(BaseModel):
    appointment_id: UUID
    clinical_notes: str | None = None
    patient_summary: str | None = None
    diagnosis: str | None = None


class ProfessionalScheduleUpdate(BaseModel):
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    slot_duration_min: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ProfessionalAppointmentStatusUpdate(BaseModel):a
    status: AppointmentStatus
    reason: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "ProfessionalAppointmentStatusUpdate":
        allowed_statuses = {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        }
        if self.status not in allowed_statuses:
            raise ValueError("status must be confirmed, completed, or no_show")
        return self


class AppointmentCancelRequest(BaseModel):
    reason: str | None = None


class ConsultationNoteUpdate(BaseModel):
    clinical_notes: str | None = None
    patient_summary: str | None = None
    diagnosis: str | None = None


class AppointmentResponse(AdminAppointmentResponse):
    pass


class ConsultationNoteResponse(ConsultationNoteCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    professional_id: UUID
    created_at: datetime
    updated_at: datetime