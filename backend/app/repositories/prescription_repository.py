from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    PatientProfile,
    Prescription,
    PrescriptionAuthorization,
    ProfessionalProfile,
    User,
)


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

    def list_for_patient_and_professional(
        self, patient_profile_id: UUID, professional_profile_id: UUID
    ) -> list[Prescription]:
        return list(
            self.session.scalars(
                select(Prescription)
                .where(
                    Prescription.patient_id == patient_profile_id,
                    Prescription.professional_id == professional_profile_id,
                )
                .order_by(Prescription.created_at.desc())
            )
        )

    def list_for_patient_view(
        self, patient_user_id: UUID, professional_user_id: UUID | None = None
    ) -> list[tuple[Prescription, Appointment, User]]:
        filters = [
            Prescription.patient_id == PatientProfile.id,
            PatientProfile.user_id == patient_user_id,
            Prescription.appointment_id == Appointment.id,
            Prescription.professional_id == ProfessionalProfile.id,
            ProfessionalProfile.user_id == Appointment.professional_id,
            User.id == ProfessionalProfile.user_id,
        ]
        if professional_user_id is not None:
            filters.append(ProfessionalProfile.user_id == professional_user_id)
        return list(
            self.session.execute(
                select(Prescription, Appointment, User)
                .select_from(Prescription)
                .join(PatientProfile, PatientProfile.id == Prescription.patient_id)
                .join(Appointment, Appointment.id == Prescription.appointment_id)
                .join(ProfessionalProfile, ProfessionalProfile.id == Prescription.professional_id)
                .join(User, User.id == ProfessionalProfile.user_id)
                .where(*filters)
                .order_by(Appointment.start_time.desc(), Prescription.created_at.desc())
            ).all()
        )

    def list_for_professional(
        self,
        professional_profile_id: UUID,
        patient_user_id: UUID | None,
        start: datetime | None,
        end: datetime | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Prescription], int]:
        filters = [Prescription.professional_id == professional_profile_id]
        if patient_user_id is not None:
            filters.append(PatientProfile.user_id == patient_user_id)
        if start is not None:
            filters.append(Prescription.created_at >= start)
        if end is not None:
            filters.append(Prescription.created_at < end)
        query = (
            select(Prescription)
            .join(PatientProfile, PatientProfile.id == Prescription.patient_id)
            .join(User, User.id == PatientProfile.user_id)
            .where(*filters)
            .order_by(Prescription.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_query = (
            select(func.count(Prescription.id))
            .join(PatientProfile, PatientProfile.id == Prescription.patient_id)
            .join(User, User.id == PatientProfile.user_id)
            .where(*filters)
        )
        return list(self.session.scalars(query)), self.session.scalar(count_query) or 0

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