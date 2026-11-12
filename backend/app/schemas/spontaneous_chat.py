from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict

from app.schemas.working_hours import ChatAvailabilityResponse


class StartSpontaneousChat(BaseModel):
    model_config = ConfigDict(extra='forbid')
    professional_id: UUID


class SpontaneousChatResponse(BaseModel):
    patient_photo_url: str | None = None
    professional_photo_url: str | None = None
    id: UUID
    patient_id: UUID
    professional_id: UUID
    patient_name: str
    professional_name: str
    status: Literal['open', 'closed']
    created_at: datetime
    updated_at: datetime
    can_write: bool
    availability: ChatAvailabilityResponse


class SpontaneousChatPage(BaseModel):
    chats: list[SpontaneousChatResponse]
    total: int
    page: int
    page_size: int


class SpontaneousMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    chat_id: UUID
    sender_id: UUID
    client_id: UUID
    content: str
    file_name: str | None
    content_type: str | None
    file_size: int | None
    created_at: datetime


class SpontaneousMessagePage(BaseModel):
    messages: list[SpontaneousMessageResponse]
    has_more: bool
