from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.appointments import ScheduleFields, ProfessionalScheduleUpdate


class WorkingHoursCreate(ScheduleFields):
    slot_duration_min: int = Field(default=30, gt=0, le=1440)
    is_active: bool = True
    model_config = ConfigDict(extra="forbid")


class WorkingHoursUpdate(ProfessionalScheduleUpdate):
    pass


class WorkingHoursBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    days_of_week: list[int] = Field(min_length=1, max_length=7)
    schedule_ids: list[UUID] = Field(default_factory=list, max_length=7)
    channel: Literal['consultation', 'chat']
    start_time: time
    end_time: time
    slot_duration_min: int = Field(default=30, gt=0, le=1440)
    is_active: bool = True

    @field_validator('days_of_week')
    @classmethod
    def valid_days(cls, days):
        if len(set(days)) != len(days) or any(day < 0 or day > 6 for day in days):
            raise ValueError('SCHEDULE_DAYS_INVALID')
        return sorted(days)

    @field_validator('schedule_ids')
    @classmethod
    def unique_ids(cls, ids):
        if len(ids) != len(set(ids)): raise ValueError('SCHEDULE_IDS_INVALID')
        return ids

    @model_validator(mode='after')
    def valid_values(self):
        WorkingHoursCreate.model_validate({**self.model_dump(exclude={'days_of_week', 'schedule_ids'}), 'day_of_week': self.days_of_week[0]})
        return self


class WorkingHoursBatchDelete(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schedule_ids: list[UUID] = Field(min_length=1, max_length=7)

    @field_validator('schedule_ids')
    @classmethod
    def unique_ids(cls, ids):
        if len(ids) != len(set(ids)): raise ValueError('SCHEDULE_IDS_INVALID')
        return ids


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
