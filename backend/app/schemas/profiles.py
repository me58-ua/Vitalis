from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import ProfessionalApprovalStatus


class PatientProfileBase(BaseModel):
    birth_date: date | None = None
    sex_at_birth: str | None = Field(default=None, max_length=30)
    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=25, le=400)
    family_history_reviewed: bool = False
    address: str | None = Field(default=None, max_length=255)
    blood_type: str | None = Field(default=None, max_length=10)
    timezone: str = Field(default="Europe/Madrid", max_length=50)
    onboarding_completed: bool = False
    share_health_data: bool = False
    ai_processing_consent: bool = False
    ai_processing_consent_at: datetime | None = None
    ai_consent_required: bool = True
    ai_consent_code: str | None = None


class PatientProfileCreate(PatientProfileBase):
    pass


class PatientProfileUpdate(BaseModel):
    address: str | None = Field(default=None, max_length=255)
    blood_type: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=50)
    onboarding_completed: bool | None = None
    share_health_data: bool | None = None
    birth_date: date | None = None
    sex_at_birth: str | None = Field(default=None, max_length=30)
    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=25, le=400)


class PatientProfileResponse(PatientProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID


class ProfessionalProfileBase(BaseModel):
    specialty: str = Field(min_length=1, max_length=150)
    bio: str | None = Field(default=None, max_length=500)
    practice_address: str | None = Field(default=None, max_length=255)
    practice_phone: str | None = Field(default=None, max_length=50)
    is_accepting_new_patients: bool = True
    default_consultation_duration_minutes: int = Field(default=30, gt=0)
    telehealth_enabled: bool = True
    license_number: str = Field(min_length=1, max_length=50)


class ProfessionalProfileCreate(ProfessionalProfileBase):
    pass


class ProfessionalProfileUpdate(BaseModel):
    specialty: str | None = Field(default=None, min_length=1, max_length=150)
    bio: str | None = Field(default=None, max_length=500)
    practice_address: str | None = Field(default=None, max_length=255)
    practice_phone: str | None = Field(default=None, max_length=50)
    is_accepting_new_patients: bool | None = None
    default_consultation_duration_minutes: int | None = Field(default=None, gt=0)
    telehealth_enabled: bool | None = None
    license_number: str | None = Field(default=None, min_length=1, max_length=50)


class ProfessionalProfileResponse(ProfessionalProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    approval_status: ProfessionalApprovalStatus
    rejection_reason: str | None
    reviewed_at: datetime | None
    reviewed_by: UUID | None


class BasicUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    tel: str | None = Field(default=None, min_length=1, max_length=32)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=50)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class PatientSummaryResponse(BaseModel):
    id: UUID
    name: str
    username: str
    gender: str | None
    email: str
    tel: str
    blood_type: str | None
    allergies_summary: str | None
    chronic_conditions_summary: str | None


class PatientListResponse(BaseModel):
    patients: list[PatientSummaryResponse]
    total: int
    page: int
    page_size: int


class ProfessionalPublicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    specialty: str
    bio: str | None
    practice_address: str | None
    practice_phone: str | None
    is_accepting_new_patients: bool
    default_consultation_duration_minutes: int
    telehealth_enabled: bool
    license_number: str


class ProfessionalListResponse(BaseModel):
    professionals: list[ProfessionalPublicResponse]
    total: int
    page: int
    page_size: int