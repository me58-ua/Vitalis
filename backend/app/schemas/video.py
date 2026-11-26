from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel
from app.models import AppointmentStatus, AppointmentType


class VideoJoinResponse(BaseModel):
    room_url: str
    token: str
    expires_at: datetime


class VideoAttendanceRequest(BaseModel):
    event: Literal["joined", "left"]


class VideoAttendanceResponse(BaseModel):
    status: AppointmentStatus


class PatientAppointmentSummary(BaseModel):
    id: UUID
    professional_id: UUID
    professional_name: str
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    status: AppointmentStatus
    appointment_reason: str | None


class PatientAppointmentPage(BaseModel):
    appointments: list[PatientAppointmentSummary]
    total: int
    page: int
    page_size: int
