import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmailStatus(str, enum.Enum):
    PENDING = "pendiente"
    SENT = "enviada"
    FAILED = "fallida"
    NOT_APPLICABLE = "no_aplica"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "recipient_id", "type", "entity_id", "scheduled_for",
            name="uq_notifications_recipient_type_entity_schedule",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_status: Mapped[EmailStatus] = mapped_column(
        Enum(
            EmailStatus,
            name="notification_email_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        server_default="no_aplica",
    )
    email_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
