from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HealthDocument


class HealthDocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, document: HealthDocument) -> HealthDocument:
        self.session.add(document)
        self.session.flush()
        return document

    def get(self, document_id: UUID) -> HealthDocument | None:
        return self.session.get(HealthDocument, document_id)

    def list_for_patient(self, patient_id: UUID) -> list[HealthDocument]:
        return list(
            self.session.scalars(
                select(HealthDocument)
                .where(HealthDocument.patient_id == patient_id)
                .order_by(HealthDocument.fecha_subida.desc())
            )
        )

    def count_for_patient(self, patient_id: UUID) -> int:
        return self.session.scalar(
            select(func.count()).select_from(HealthDocument).where(HealthDocument.patient_id == patient_id)
        ) or 0