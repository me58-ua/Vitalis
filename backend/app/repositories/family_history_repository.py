from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FamilyHistoryEntry


class FamilyHistoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, entry: FamilyHistoryEntry) -> FamilyHistoryEntry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_for_patient(self, patient_id: UUID) -> list[FamilyHistoryEntry]:
        return list(
            self.session.scalars(
                select(FamilyHistoryEntry)
                .where(FamilyHistoryEntry.patient_id == patient_id)
                .order_by(FamilyHistoryEntry.recorded_date, FamilyHistoryEntry.id)
            )
        )

    def get_for_patient(self, patient_id: UUID, entry_id: int) -> FamilyHistoryEntry | None:
        return self.session.scalar(
            select(FamilyHistoryEntry).where(
                FamilyHistoryEntry.patient_id == patient_id,
                FamilyHistoryEntry.id == entry_id,
            )
        )

    def delete(self, entry: FamilyHistoryEntry) -> None:
        self.session.delete(entry)
        self.session.flush()
