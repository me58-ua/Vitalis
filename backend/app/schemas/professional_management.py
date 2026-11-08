from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class TimeBlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    start_time: AwareDatetime
    end_time: AwareDatetime
    reason: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_time <= self.start_time:
            raise ValueError("El fin debe ser posterior al inicio")
        return self


class TimeBlockResponse(TimeBlockCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    professional_id: UUID
    created_at: datetime


class ProfileChangeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    reason: str | None = Field(default=None, max_length=1000)
