from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import AppointmentStatus


class ChatParticipant(BaseModel):
    id: UUID
    role: str


class ChatRoomResponse(BaseModel):
    appointment_id: UUID
    participants: list[ChatParticipant]
    can_write: bool
    status: AppointmentStatus


class ChatMessageCreate(BaseModel):
    content: str = Field(max_length=2000)


class ChatMessageResponse(BaseModel):
    id: UUID
    appointment_id: UUID
    sender_id: UUID
    content: str
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]
