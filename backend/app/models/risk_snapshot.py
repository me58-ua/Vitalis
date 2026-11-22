import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RiskSnapshotModel(str, enum.Enum):
    BMI = "bmi"
    AUDIT_C = "audit_c"
    TOBACCO = "tobacco"
    SEDENTARY = "sedentary"
    SLEEP = "sleep"
    FAMILY_DIABETES = "family_diabetes"
    FAMILY_CANCER = "family_cancer"
    FAMILY_CARDIOVASCULAR = "family_cardiovascular"
    FAMILY_HUNTINGTON = "family_huntington"
    FAMILY_OTHER = "family_other"
    FAMILY_HYPERTENSION = "family_hypertension"
    FAMILY_HIGH_CHOLESTEROL = "family_high_cholesterol"
    FAMILY_STROKE = "family_stroke"
    FAMILY_OSTEOPOROSIS = "family_osteoporosis"
    FAMILY_CYSTIC_FIBROSIS = "family_cystic_fibrosis"
    FAMILY_SICKLE_CELL_DISEASE = "family_sickle_cell_disease"
    FAMILY_FAMILIAL_HYPERCHOLESTEROLEMIA = "family_familial_hypercholesterolemia"


class RiskSnapshotTrigger(str, enum.Enum):
    ONBOARDING = "onboarding"
    HABIT_CHANGE = "habit_change"
    BODY_CHANGE = "body_change"
    FAMILY_CHANGE = "family_change"


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    __table_args__ = (
        Index("ix_risk_snapshots_patient_model_computed", "patient_id", "model", "computed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[RiskSnapshotModel] = mapped_column(
        Enum(RiskSnapshotModel, name="risk_snapshot_model", native_enum=False,
             values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    metric_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    alert_level: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger: Mapped[RiskSnapshotTrigger] = mapped_column(
        Enum(RiskSnapshotTrigger, name="risk_snapshot_trigger", native_enum=False,
             values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    patient_profile = relationship("PatientProfile")
