from datetime import date, datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.family_history import HereditaryConditions, FamilyRelationship
from app.models.health import AllergySeverity, HabitType
from app.schemas.health_documents import HealthDocumentResponse


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


class AppointmentHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    professional_id: UUID
    start_time: datetime
    end_time: datetime
    status: str
    type: str
    appointment_reason: str | None = Field(default=None, validation_alias=AliasChoices("appointment_reason", "reason"))
    cancellation_reason: str | None = None


class ClinicalNoteHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_id: UUID
    professional_id: UUID
    clinical_notes: str | None
    patient_summary: str | None
    diagnosis: str | None
    created_at: datetime
    updated_at: datetime


class PrescriptionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_id: UUID
    patient_id: UUID
    professional_id: UUID
    file_url: str
    notas: str | None
    created_at: datetime


class AlcoholLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: UUID
    frequency: int
    quantity: int | None
    binge: int | None
    date: date
    recorded_at: datetime


class FamilyHistoryCreate(BaseModel):
    relationship: FamilyRelationship
    condition_category: HereditaryConditions
    detail: str | None = Field(default=None, max_length=150)
    age_at_diagnosis: int | None = Field(default=None, ge=0, le=120)
    recorded_date: date


class FamilyHistoryResponse(FamilyHistoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: UUID
    created_at: datetime


class HealthSnapshot(BaseModel):
    consent_shared: bool
    message_code: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    sex_at_birth: str | None = None
    allergies: list[AllergyResponse] = []
    chronic_conditions: list[ChronicConditionResponse] = []
    medications: list[MedicationResponse] = []
    habit_logs: list[HabitLogResponse] = []
    alcohol_logs: list[AlcoholLogResponse] = []
    family_history_entries: list[FamilyHistoryResponse] = []
    health_documents: list[HealthDocumentResponse] = []
    appointments: list[AppointmentHistoryResponse] = []
    clinical_notes: list[ClinicalNoteHistoryResponse] = []
    prescriptions: list[PrescriptionHistoryResponse] = []


class ConsentUpdate(BaseModel):
    share_health_data: bool


class AIConsentUpdate(BaseModel):
    ai_processing_consent: bool


class AlcoholLogHistoryResponse(BaseModel):
    alcohol_logs: list[AlcoholLogResponse]
    next_cursor: int | None = None


class OnboardingMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    block: str = Field(min_length=1, max_length=40)
    question_id: str | None = Field(default=None, max_length=60)


class OnboardingFamilyHistoryConfirmation(BaseModel):
    confirmed: bool


class OnboardingMessageResponse(BaseModel):
    block: str
    next_question_code: str
    saved: bool
    onboarding_completed: bool


class OnboardingSkipResponse(BaseModel):
    onboarding_completed: bool
    next_question_code: str | None = None
    last_question_id: str | None = None
    family_history_confirmation_pending: bool = False
