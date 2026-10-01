from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import HabitType


class HabitHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: UUID
    habit_type: HabitType
    value: float | None
    unit: str
    date: date


class HabitAggregateResponse(BaseModel):
    habit_type: HabitType
    count: int
    numeric_count: int
    sum: float | None
    average: float | None
    minimum: float | None
    maximum: float | None


class HabitHistoryListResponse(BaseModel):
    habits: list[HabitHistoryResponse]
    total: int
    page: int
    page_size: int
    aggregates: list[HabitAggregateResponse]