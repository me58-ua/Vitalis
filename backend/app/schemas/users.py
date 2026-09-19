from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import UserRole


class AdminUserCreate(BaseModel):
    dni: str = Field(min_length=5, max_length=20)
    name: str = Field(min_length=1, max_length=150)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    tel: str = Field(min_length=1, max_length=32)
    birth_date: date
    gender: str | None = Field(default=None, max_length=50)
    role: UserRole

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