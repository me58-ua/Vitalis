import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    allergies_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chronic_conditions_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Europe/Madrid")

    user = relationship("User", back_populates="patient_profile")