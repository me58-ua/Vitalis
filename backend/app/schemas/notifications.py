from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    type: str
    title: str
    message: str
    entity: str | None
    entity_id: UUID | None
    scheduled_for: datetime | None
    read_at: datetime | None
    email_required: bool
    email_status: str
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    next_cursor: UUID | None = None


class UnreadCountResponse(BaseModel):
    count: int


class ReadAllResponse(BaseModel):
    marked_read: int
