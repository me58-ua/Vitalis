from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import UserRole


class UserRegisterRequest(BaseModel):
    role: UserRole
    name: str = Field(min_length=1, max_length=150)
    dni: str = Field(min_length=5, max_length=20)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    tel: str = Field(min_length=1, max_length=32)
    birth_date: date
    gender: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=255)
    blood_type: str | None = Field(default=None, max_length=10)
    height_cm: float | None = Field(default=None, ge=100, le=250, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, ge=25, le=400, allow_inf_nan=False)
    timezone: str = Field(default="Europe/Madrid", max_length=50)
    specialty: str | None = Field(default=None, max_length=150)
    bio: str | None = Field(default=None, max_length=500)
    practice_address: str | None = Field(default=None, max_length=255)
    practice_phone: str | None = Field(default=None, max_length=50)
    is_accepting_new_patients: bool | None = None
    default_consultation_duration_minutes: int | None = Field(default=None, gt=0)
    telehealth_enabled: bool | None = None
    license_number: str | None = Field(default=None, max_length=50)
    terms_accepted: bool = Field(description="Must be true to create an account")

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
        value = value.strip().lower()
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("username may contain only letters, numbers, underscores, and hyphens")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("must be a valid email address")
        return value

    @field_validator("terms_accepted")
    @classmethod
    def require_terms_acceptance(cls, value: bool) -> bool:
        if not value:
            raise ValueError("terms and conditions must be accepted")
        return value

    @model_validator(mode="after")
    def validate_role_fields(self) -> "UserRegisterRequest":
        if self.role == UserRole.ADMIN:
            raise ValueError("public registration is only available for patients and professionals")
        if self.role == UserRole.PROFESSIONAL:
            required_fields = (
                "specialty",
                "bio",
                "practice_address",
                "practice_phone",
                "is_accepting_new_patients",
                "default_consultation_duration_minutes",
                "telehealth_enabled",
                "license_number",
            )
            missing = [field for field in required_fields if getattr(self, field) is None]
            if missing:
                raise ValueError(
                    "professional registration requires: " + ", ".join(missing)
                )
        return self


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("must be a valid email address")
        return value


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
