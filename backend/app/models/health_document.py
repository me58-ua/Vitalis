import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HealthDocumentType(str, Enum):
    REPORT = "informe"
    LABORATORY = "analitica"
    OTHER = "otro"


class HealthDocument(Base):
    __tablename__ = "health_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[HealthDocumentType] = mapped_column(String(20), nullable=False, index=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_subida: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    patient_profile = relationship("PatientProfile", back_populates="health_documents")