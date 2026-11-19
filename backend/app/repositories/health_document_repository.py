from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import HealthDocument, PatientProfile
from app.repositories.appointment_repository import latest_health_sharing


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

    def search_for_patient(self, user_id, query, document_type, offset, limit):
        return self._search(
            PatientProfile.user_id == user_id, query, document_type, offset, limit
        )

    def search_for_professional(self, professional_id, query, document_type, offset, limit):
        return self._search(
            PatientProfile.share_health_data.is_(True)
            & (latest_health_sharing(PatientProfile.user_id, professional_id) == "full"),
            query, document_type, offset, limit,
        )

    def _search(self, scope, query, document_type, offset, limit):
        # Treat wildcard characters as literal user text, not LIKE operators.
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pattern = f"%{escaped}%"
        filters = [scope, or_(
            HealthDocument.descripcion.ilike(pattern, escape='\\'),
            HealthDocument.tipo.ilike(pattern, escape='\\'),
        )]
        if document_type is not None:
            filters.append(HealthDocument.tipo == document_type)
        join = HealthDocument.patient_id == PatientProfile.id
        total = self.session.scalar(
            select(func.count()).select_from(HealthDocument).join(PatientProfile, join).where(*filters)
        ) or 0
        rows = self.session.execute(
            select(HealthDocument, PatientProfile.user_id).join(PatientProfile, join)
            .where(*filters)
            .order_by(HealthDocument.fecha_subida.desc(), HealthDocument.id.desc())
            .offset(offset).limit(limit)
        ).all()
        return rows, total
