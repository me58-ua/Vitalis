from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Prescription, PrescriptionAuthorization


class PrescriptionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_appointment(self, appointment_id: UUID) -> Prescription | None:
        return self.session.scalar(
            select(Prescription).where(Prescription.appointment_id == appointment_id)
        )

    def get_authorization(self, appointment_id: UUID) -> PrescriptionAuthorization | None:
        return self.session.scalar(
            select(PrescriptionAuthorization).where(
                PrescriptionAuthorization.appointment_id == appointment_id
            )
        )

    def create(self, prescription: Prescription) -> Prescription:
        self.session.add(prescription)
        self.session.flush()
        return prescription

    def update(self, prescription: Prescription, values: dict) -> Prescription:
        for field, value in values.items():
            setattr(prescription, field, value)
        self.session.flush()
        return prescription

    def create_authorization(
        self, authorization: PrescriptionAuthorization
    ) -> PrescriptionAuthorization:
        self.session.add(authorization)
        self.session.flush()
        return authorization

    def rollback(self) -> None:
        self.session.rollback()