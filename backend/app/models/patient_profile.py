import uuid

from sqlalchemy import Boolean, ForeignKey, String
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
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Europe/Madrid")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    share_health_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    user = relationship("User", back_populates="patient_profile")
    allergies = relationship("Allergy", back_populates="patient_profile", cascade="all, delete-orphan")
    chronic_conditions = relationship(
        "ChronicCondition", back_populates="patient_profile", cascade="all, delete-orphan"
    )
    medications = relationship("Medication", back_populates="patient_profile", cascade="all, delete-orphan")
    habit_logs = relationship("HabitLog", back_populates="patient_profile", cascade="all, delete-orphan")
    health_documents = relationship("HealthDocument", back_populates="patient_profile", cascade="all, delete-orphan")