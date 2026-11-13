import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"
    __table_args__ = (
        CheckConstraint("tipo IS NULL OR tipo IN ('medicacion', 'prueba', 'otro')", name="ck_prescriptions_tipo"),
        CheckConstraint("fecha_caducidad IS NULL OR (fecha_emision IS NOT NULL AND fecha_caducidad >= fecha_emision)", name="ck_prescriptions_dates"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professional_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    titulo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_caducidad: Mapped[date | None] = mapped_column(Date, nullable=True)
    codigo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PrescriptionAuthorization(Base):
    __tablename__ = "prescription_authorizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    authorized_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
