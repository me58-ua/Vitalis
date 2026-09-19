import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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

    user = relationship("User", back_populates="professional_profile")