import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AllergySeverity(str, enum.Enum):
    MILD = "leve"
    MODERATE = "moderada"
    SEVERE = "grave"
    LIFE_THREATENING = "mortal"


class HabitType(str, enum.Enum):
    SLEEP = "sueno"
    EXERCISE = "ejercicio"
    DIET = "dieta"
    TOBACCO = "tabaco"
    ALCOHOL = "alcohol"


class Allergy(Base):
    __tablename__ = "allergies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column("nombre", String(150), nullable=False)
    severity: Mapped[AllergySeverity] = mapped_column(
        "gravedad", Enum(AllergySeverity, name="allergy_severity", values_callable=lambda values: [value.value for value in values]), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column("fecha_registro", DateTime(timezone=True), server_default=func.now(), nullable=False)
    patient_profile = relationship("PatientProfile", back_populates="allergies")


class ChronicCondition(Base):
    __tablename__ = "chronic_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    condition_name: Mapped[str] = mapped_column("nombre_condicion", String(200), nullable=False)
    diagnosis_date: Mapped[date | None] = mapped_column("fecha_diagnostico", Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    recorded_at: Mapped[datetime] = mapped_column("fecha_registro", DateTime(timezone=True), server_default=func.now(), nullable=False)
    patient_profile = relationship("PatientProfile", back_populates="chronic_conditions")


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column("nombre", String(200), nullable=False)
    dosage: Mapped[str] = mapped_column("dosis", String(150), nullable=False)
    frequency: Mapped[str] = mapped_column("frecuencia", String(150), nullable=False)
    start_date: Mapped[date | None] = mapped_column("fecha_inicio", Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column("fecha_fin", Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    recorded_at: Mapped[datetime] = mapped_column("fecha_registro", DateTime(timezone=True), server_default=func.now(), nullable=False)
    patient_profile = relationship("PatientProfile", back_populates="medications")


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True)
    habit_type: Mapped[HabitType] = mapped_column(
        "tipo", Enum(HabitType, name="habit_type", values_callable=lambda values: [value.value for value in values]), nullable=False
    )
    value: Mapped[float | None] = mapped_column("valor", Numeric, nullable=True)
    unit: Mapped[str] = mapped_column("unidad", String(50), nullable=False)
    date: Mapped[date] = mapped_column("fecha", Date, nullable=False)
    patient_profile = relationship("PatientProfile", back_populates="habit_logs")