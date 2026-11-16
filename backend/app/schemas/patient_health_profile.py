from pydantic import BaseModel

from app.schemas.profiles import PatientProfileResponse
from app.schemas.health import (
    AllergyResponse, ChronicConditionResponse,
    MedicationResponse, HabitLogResponse,
    FamilyHistoryResponse, AlcoholLogResponse,
)


class AlcoholCurrent(BaseModel):
    frequency: int | None = None
    quantity: int | None = None
    binge: int | None = None


class PatientHealthProfileResponse(BaseModel):
    profile: PatientProfileResponse
    allergies: list[AllergyResponse]
    chronic_conditions: list[ChronicConditionResponse]
    medications: list[MedicationResponse]
    habit_logs: list[HabitLogResponse]
    family_history_entries: list[FamilyHistoryResponse]
    alcohol_logs: list[AlcoholLogResponse]
    alcohol_current: AlcoholCurrent | None = None
    declarations: dict[str, str]
    onboarding_stage: str
