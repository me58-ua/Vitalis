import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProfessionalApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProfessionalProfile(Base):
    __tablename__ = "professional_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    specialty: Mapped[str] = mapped_column(String(150), nullable=False)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    practice_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    practice_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_accepting_new_patients: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_consultation_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    telehealth_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    license_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    approval_status: Mapped[ProfessionalApprovalStatus] = mapped_column(
        Enum(
            ProfessionalApprovalStatus,
            name="professional_approval_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=ProfessionalApprovalStatus.PENDING,
        server_default="pending",
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    pending_changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    change_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    change_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    change_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship(
        "User",
        back_populates="professional_profile",
        foreign_keys=[user_id],
    )
