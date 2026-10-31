from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from app.models import AppointmentStatus, AppointmentType


class ProfessionalAppointmentsQuery(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    status: AppointmentStatus | None = None
    upcoming_only: bool = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before or equal to to_date")
        return self


class ProfessionalAppointmentSummary(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str
    patient_username: str
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    status: AppointmentStatus
    appointment_reason: str | None
    cancellation_reason: str | None


class ProfessionalAppointmentsResponse(BaseModel):
    appointments: list[ProfessionalAppointmentSummary]
    total: int
    page: int
    page_size: int


class WeeklyAppointmentCount(BaseModel):
    date: date
    count: int


class ProfessionalDashboardResponse(BaseModel):
    timezone: str = "Europe/Madrid"
    generated_at: datetime
    date: date
    week_start: date
    week_end: date
    appointments_today: int
    appointments_yesterday: int
    scheduled_today: int
    completed_today: int
    assigned_patients: int
    weekly_distribution: list[WeeklyAppointmentCount]
    upcoming_appointments: list[ProfessionalAppointmentSummary]
    upcoming_total: int
