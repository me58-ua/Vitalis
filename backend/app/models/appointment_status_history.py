import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.appointment import AppointmentStatus


class AppointmentStatusHistory(Base):
    __tablename__ = "appointment_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True
    )
    old_status: Mapped[AppointmentStatus | None] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            native_enum=True,
            values_callable=lambda statuses: [status.value for status in statuses],
            create_type=False,
        ),
        nullable=True,
    )
    new_status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            native_enum=True,
            values_callable=lambda statuses: [status.value for status in statuses],
            create_type=False,
        ),
        nullable=False,
    )
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )