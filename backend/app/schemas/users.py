from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import UserRole
from app.schemas.profiles import ProfessionalProfileCreate, ProfessionalProfileResponse


class AdminPatientProfileInput(BaseModel):
    address: str | None = Field(default=None, max_length=255)
    blood_type: str | None = Field(default=None, max_length=10)
    timezone: str = Field(default="Europe/Madrid", min_length=1, max_length=50)
    sex_at_birth: str | None = Field(default=None, max_length=30)
    height_cm: float | None = Field(default=None, ge=100, le=250, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, ge=25, le=400, allow_inf_nan=False)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("INVALID_TIMEZONE") from error
        return value


class AdminProfessionalProfileInput(ProfessionalProfileCreate):
    @field_validator("specialty", "license_number")
    @classmethod
    def required_profile_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value


class AdminUserCreate(BaseModel):
    photo_url: str | None = Field(default=None, max_length=2048, pattern=r"^https://[^\s]+$")
    dni: str = Field(min_length=5, max_length=20)
    name: str = Field(min_length=1, max_length=150)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    tel: str = Field(min_length=1, max_length=32)
    birth_date: date
    gender: str | None = Field(default=None, max_length=50)
    role: UserRole
    patient_profile: AdminPatientProfileInput | None = None
    professional_profile: AdminProfessionalProfileInput | None = None

    @model_validator(mode="after")
    def validate_profile_role(self) -> "AdminUserCreate":
        if self.role == UserRole.PROFESSIONAL and self.professional_profile is None:
            raise ValueError("PROFESSIONAL_PROFILE_REQUIRED")
        if self.patient_profile is not None and self.role != UserRole.PATIENT:
            raise ValueError("PROFILE_ROLE_MISMATCH")
        if self.professional_profile is not None and self.role != UserRole.PROFESSIONAL:
            raise ValueError("PROFILE_ROLE_MISMATCH")
        return self

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: UserRole | str) -> UserRole | str:
        return value.lower() if isinstance(value, str) else value

    @field_validator("name", "dni", "username", "email", "tel")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("dni")
    @classmethod
    def normalize_dni(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.lower()
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("username may contain only letters, numbers, underscores, and hyphens")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("must be a valid email address")
        return value


class AdminUserUpdate(BaseModel):
    photo_url: str | None = Field(default=None, max_length=2048, pattern=r"^https://[^\s]+$")
    dni: str | None = Field(default=None, min_length=5, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    tel: str | None = Field(default=None, min_length=1, max_length=32)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    role: UserRole | None = None
    is_active: bool | None = None
    patient_profile: AdminPatientProfileInput | None = None
    professional_profile: AdminProfessionalProfileInput | None = None

    @model_validator(mode="after")
    def reject_required_nulls(self) -> "AdminUserUpdate":
        required = {"dni", "name", "username", "email", "password", "tel", "birth_date", "role", "is_active", "patient_profile", "professional_profile"}
        if any(getattr(self, key) is None for key in self.model_fields_set & required):
            raise ValueError("REQUIRED_FIELD_NULL")
        return self

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: UserRole | str | None) -> UserRole | str | None:
        return value.lower() if isinstance(value, str) else value

    @field_validator("name", "dni", "username", "email", "tel")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("dni")
    @classmethod
    def normalize_dni(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.lower()
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("username may contain only letters, numbers, underscores, and hyphens")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("must be a valid email address")
        return value


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    photo_url: str | None = None

    id: UUID
    name: str
    dni: str
    username: str
    email: str
    tel: str
    birth_date: date
    gender: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminUserDetailResponse(AdminUserResponse):
    patient_profile: AdminPatientProfileInput | None = None
    professional_profile: ProfessionalProfileResponse | None = None
