from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.health import AllergySeverity, HabitType


class HealthRecordBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: UUID


class AllergyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    severity: AllergySeverity


class AllergyResponse(HealthRecordBase, AllergyCreate):
    recorded_at: datetime


class ChronicConditionCreate(BaseModel):
    condition_name: str = Field(min_length=1, max_length=200)
    diagnosis_date: date | None = None
    active: bool = True


class ChronicConditionResponse(HealthRecordBase, ChronicConditionCreate):
    recorded_at: datetime


class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dosage: str = Field(min_length=1, max_length=150)
    frequency: str = Field(min_length=1, max_length=150)
    start_date: date | None = None
    end_date: date | None = None
    active: bool = True


class MedicationResponse(HealthRecordBase, MedicationCreate):
    recorded_at: datetime


class HabitLogCreate(BaseModel):
    habit_type: HabitType
    value: float | None = None
    unit: str = Field(min_length=1, max_length=50)
    date: date


class HabitLogResponse(HealthRecordBase, HabitLogCreate):
    pass


class HealthSnapshot(BaseModel):
    consent_shared: bool
    message: str | None = None
    allergies: list[AllergyResponse] = []
    chronic_conditions: list[ChronicConditionResponse] = []
    medications: list[MedicationResponse] = []
    habit_logs: list[HabitLogResponse] = []


class ConsentUpdate(BaseModel):
    share_health_data: bool


class OnboardingMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    block: str = Field(min_length=1, max_length=40)


class OnboardingMessageResponse(BaseModel):
    block: str
    next_question: str
    saved: bool
    onboarding_completed: bool


class OnboardingSkipResponse(BaseModel):
    onboarding_completed: bool