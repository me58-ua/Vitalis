import enum
import secrets
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import literal_column

from app.database import Base


class AppointmentType(str, enum.Enum):
    VIDEO = "video"
    IN_PERSON = "in_person"


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="valid_time_range"),
        ExcludeConstraint(
            ("professional_id", "="),
            (literal_column("tstzrange(start_time, end_time)"), "&&"),
            where=text("status != 'cancelled'"),
            using="gist",
            name="no_overlapping_appointments",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            native_enum=True,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=AppointmentStatus.PENDING,
        server_default="pending",
    )
    type: Mapped[AppointmentType] = mapped_column(
        Enum(
            AppointmentType,
            name="appointment_type",
            native_enum=True,
            values_callable=lambda types: [appointment_type.value for appointment_type in types],
        ),
        nullable=False,
        default=AppointmentType.VIDEO,
        server_default="video",
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(24),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )