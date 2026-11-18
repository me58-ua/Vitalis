from datetime import date, datetime, time
from uuid import UUID
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator, field_validator

from app.models import AppointmentStatus, AppointmentType

ScheduleChannel = Literal["in_person", "video", "chat"]


class ScheduleFields(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    slot_duration_min: int = Field(gt=0, le=1440)
    is_active: bool
    channel: ScheduleChannel = "in_person"

    @field_validator("start_time", "end_time")
    @classmethod
    def local_clock(cls, value):
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("SCHEDULE_LOCAL_MINUTES_REQUIRED")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> "ScheduleFields":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        duration = (self.end_time.hour * 60 + self.end_time.minute) - (self.start_time.hour * 60 + self.start_time.minute)
        if self.channel != "chat" and self.slot_duration_min > duration:
            raise ValueError("SCHEDULE_SLOT_TOO_LONG")
        return self


class AdminScheduleCreate(ScheduleFields):
    professional_id: UUID


class AdminScheduleResponse(AdminScheduleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class ProfessionalScheduleResponse(AdminScheduleResponse):
    pass


class AdminAppointmentCreate(BaseModel):
    patient_id: UUID
    professional_id: UUID
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    appointment_reason: str | None = Field(default=None, validation_alias=AliasChoices("appointment_reason", "reason"))

    @model_validator(mode="after")
    def validate_appointment(self) -> "AdminAppointmentCreate":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AdminAppointmentResponse(AdminAppointmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: AppointmentStatus
    room_id: str | UUID
    created_at: datetime
    updated_at: datetime
    cancellation_reason: str | None = None


class AdminAppointmentUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: AppointmentStatus | None = None
    type: AppointmentType | None = None
    appointment_reason: str | None = None
    cancellation_reason: str | None = None
    status_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def legacy_reason(cls, value):
        if isinstance(value, dict) and "reason" in value:
            value = dict(value)
            key = "cancellation_reason" if value.get("status") == "cancelled" else "status_reason" if value.get("status") else "appointment_reason"
            value.setdefault(key, value.pop("reason"))
        return value

    @model_validator(mode="after")
    def validate_times(self) -> "AdminAppointmentUpdate":
        if self.start_time is not None and self.start_time.tzinfo is None:
            raise ValueError("start_time must include a timezone")
        if self.end_time is not None and self.end_time.tzinfo is None:
            raise ValueError("end_time must include a timezone")
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        return self


class ProfessionalAppointmentCreate(BaseModel):
    patient_id: UUID
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    appointment_reason: str | None = Field(default=None, validation_alias=AliasChoices("appointment_reason", "reason"))

    @model_validator(mode="after")
    def validate_appointment(self) -> "ProfessionalAppointmentCreate":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ConsultationNoteCreate(BaseModel):
    appointment_id: UUID
    clinical_notes: str | None = None
    patient_summary: str | None = None
    diagnosis: str | None = None


class ProfessionalScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    slot_duration_min: int | None = Field(default=None, gt=0, le=1440)
    is_active: bool | None = None
    channel: ScheduleChannel | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def local_clock(cls, value):
        if value is not None and (value.tzinfo is not None or value.second or value.microsecond):
            raise ValueError("SCHEDULE_LOCAL_MINUTES_REQUIRED")
        return value

    @model_validator(mode="after")
    def required_values(self):
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("REQUIRED_FIELD_NULL")
        return self


class ProfessionalAppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    status_reason: str | None = Field(default=None, validation_alias=AliasChoices("status_reason", "reason"))

    @model_validator(mode="after")
    def validate_status(self) -> "ProfessionalAppointmentStatusUpdate":
        allowed_statuses = {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        }
        if self.status not in allowed_statuses:
            raise ValueError("status must be confirmed, completed, or no_show")
        return self


class AppointmentCancelRequest(BaseModel):
    cancellation_reason: str | None = Field(default=None, validation_alias=AliasChoices("cancellation_reason", "reason"))


class ConsultationNoteUpdate(BaseModel):
    clinical_notes: str | None = None
    patient_summary: str | None = None
    diagnosis: str | None = None


class AppointmentFollowUpNotes(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)

    shared_diagnosis: str | None = Field(max_length=2000)
    shared_notes: str | None = Field(max_length=10000)
    clinical_notes: str | None


class ProfessionalAppointmentFollowUp(AppointmentFollowUpNotes):
    id: UUID
    patient_id: UUID
    patient_name: str
    start_time: datetime
    appointment_reason: str | None
    status: Literal["completed"] = "completed"
    can_edit_notes: bool


class PatientAppointmentFollowUp(BaseModel):
    appointment_id: UUID
    start_time: datetime
    appointment_reason: str | None
    professional_name: str
    shared_diagnosis: str | None
    shared_notes: str | None
    has_prescription: bool


class AppointmentResponse(AdminAppointmentResponse):
    pass


class ProfessionalAppointmentHistoryResponse(AdminAppointmentResponse):
    patient_name: str
    patient_username: str
    patient_email: str
    clinical_notes: str | None = None
    patient_summary: str | None = None
    diagnosis: str | None = None


class ProfessionalAppointmentHistoryListResponse(BaseModel):
    appointments: list[ProfessionalAppointmentHistoryResponse]
    total: int
    page: int
    page_size: int


class ConsultationNoteResponse(ConsultationNoteCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    professional_id: UUID
    created_at: datetime
    updated_at: datetime


class PatientAppointmentCreate(BaseModel):
    professional_id: UUID
    start_time: datetime
    end_time: datetime
    type: AppointmentType
    appointment_reason: str | None = Field(default=None, validation_alias=AliasChoices("appointment_reason", "reason"))

    @model_validator(mode="after")
    def validate_appointment(self) -> "PatientAppointmentCreate":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilitySlot(BaseModel):
    start_time: datetime
    end_time: datetime
    type: AppointmentType


class AvailabilityResponse(BaseModel):
    professional_id: UUID
    date: date
    slots: list[AvailabilitySlot]
