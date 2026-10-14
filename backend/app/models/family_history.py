import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.database import Base


class FamilyRelationship(str, enum.Enum):
    MOTHER = "madre"
    FATHER = "padre"
    SIBLING = "hermano"
    CHILD = "hijo"
    GRANDPARENT = "abuelo"
    UNCLE = "tio"
    OTHER = "otro"

# i will extend this enum with additional hereditary conditions
class HeredataryConditions(str, enum.Enum):
    DIABETES = "diabetes"
    CANCER = "cancer"
    CARDIOVASCULAR = "cardiovascular"
    HUNTINGTON = "huntington"
    OTHER = "otro"


class FamilyHistoryEntry(Base):
    __tablename__ = "family_history_entries"
    __table_args__ = (
        CheckConstraint("age_at_diagnosis BETWEEN 0 AND 120", name="ck_family_history_age_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship: Mapped[FamilyRelationship] = mapped_column(
        Enum(
            FamilyRelationship,
            name="family_relationship",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    condition_category: Mapped[HeredataryConditions] = mapped_column(
        Enum(
            HeredataryConditions,
            name="family_condition_category",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    detail: Mapped[str | None] = mapped_column(String(150), nullable=True)
    age_at_diagnosis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    patient_profile = orm_relationship("PatientProfile", back_populates="family_history_entries")
