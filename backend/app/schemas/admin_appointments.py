from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from app.models import AppointmentStatus, AppointmentType


class AdminAppointmentsQuery(BaseModel):
    patient_id: UUID | None = None
    professional_id: UUID | None = None
    from_date: date | None = None
    to_date: date | None = None
    upcoming_month: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before or equal to to_date")
        return self


class AdminAppointmentSummary(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str
    professional_id: UUID
    professional_name: str
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    status: AppointmentStatus
    reason: str | None


class AdminAppointmentListResponse(BaseModel):
    appointments: list[AdminAppointmentSummary]
    total: int
    page: int
    page_size: int


class AdminUpcomingAppointmentsResponse(BaseModel):
    appointments: list[AdminAppointmentSummary]
    total: int
    period_start: datetime
    period_end: datetime
    timezone: str = "Europe/Madrid"
