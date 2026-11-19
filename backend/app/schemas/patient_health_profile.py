from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from app.models import FamilyHistoryStatus
from app.schemas.appointments import PatientAppointmentFollowUp

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


class ProfessionalHealthSharing(BaseModel):
    professional_id: UUID
    professional_name: str
    scope: Literal["basic", "full"]


class PatientHealthProfileResponse(BaseModel):
    appointment_follow_ups: list[PatientAppointmentFollowUp]
    family_history_status: FamilyHistoryStatus = FamilyHistoryStatus.NOT_COLLECTED
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
