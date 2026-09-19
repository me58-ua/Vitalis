from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientProfileBase(BaseModel):
    address: str | None = Field(default=None, max_length=255)
    blood_type: str | None = Field(default=None, max_length=10)
    allergies_summary: str | None = Field(default=None, max_length=255)
    chronic_conditions_summary: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="Europe/Madrid", max_length=50)
    language_preference: str = Field(default="es", max_length=10)


class PatientProfileCreate(PatientProfileBase):
    pass


class PatientProfileUpdate(BaseModel):
    address: str | None = Field(default=None, max_length=255)
    blood_type: str | None = Field(default=None, max_length=10)
    allergies_summary: str | None = Field(default=None, max_length=255)
    chronic_conditions_summary: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=50)
    language_preference: str | None = Field(default=None, max_length=10)


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


class ProfessionalProfileResponse(ProfessionalProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID


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


class ProfessionalListResponse(BaseModel):
    professionals: list[ProfessionalPublicResponse]
    total: int
    page: int
    page_size: int