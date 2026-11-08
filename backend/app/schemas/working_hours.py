from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.appointments import AdminScheduleCreate, ProfessionalScheduleUpdate


class WorkingHoursCreate(AdminScheduleCreate):
    # Ownership is always taken from the authenticated account, never the body.
    professional_id: UUID = Field(default=UUID(int=0), exclude=True)
    slot_duration_min: int = Field(default=30, gt=0, le=1440)
    is_active: bool = True
    model_config = ConfigDict(extra="forbid")


class WorkingHoursUpdate(ProfessionalScheduleUpdate):
    pass


class WorkingHoursResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    professional_id: UUID
    channel: Literal['consultation', 'chat']
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_min: int
    is_active: bool
    created_at: datetime


class ChatAvailabilityResponse(BaseModel):
    professional_id: UUID
    available: bool
    reason: Literal['available', 'outside_hours', 'blocked', 'busy', 'unavailable']
    timezone: str = 'Europe/Madrid'
    evaluated_at: datetime
    closes_at: datetime | None = None
