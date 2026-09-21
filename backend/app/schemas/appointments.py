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