from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import PatientProfile, ProfessionalPatient, ProfessionalProfile, User, UserRole


class ProfessionalRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_patients(
        self,
        professional_id: UUID,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[User, PatientProfile]], int]:
        filters = [
            ProfessionalPatient.professional_id == professional_id,
            User.id == ProfessionalPatient.patient_id,
            User.role == UserRole.PATIENT,
        ]
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    User.name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.username.ilike(search_pattern),
                )
            )
        query = (
            select(User, PatientProfile)
            .join(ProfessionalPatient, ProfessionalPatient.patient_id == User.id)
            .join(PatientProfile, PatientProfile.user_id == User.id)
            .where(*filters)
            .order_by(User.name.asc())
            .offset(offset)
            .limit(limit)
        )
        count_query = (
            select(func.count())
            .select_from(User)
            .join(ProfessionalPatient, ProfessionalPatient.patient_id == User.id)
            .where(*filters)
        )
        return list(self.session.execute(query).all()), self.session.scalar(count_query) or 0

    def list_professionals(
        self,
        name: str | None,
        specialty: str | None,
        is_accepting_new_patients: bool | None,
        telehealth_enabled: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[User, ProfessionalProfile]], int]:
        filters = [User.role == UserRole.PROFESSIONAL, User.is_active.is_(True)]
        if name:
            filters.append(User.name.ilike(f"%{name}%"))
        if specialty:
            filters.append(ProfessionalProfile.specialty.ilike(f"%{specialty}%"))
        if is_accepting_new_patients is not None:
            filters.append(
                ProfessionalProfile.is_accepting_new_patients.is_(is_accepting_new_patients)
            )
        if telehealth_enabled is not None:
            filters.append(ProfessionalProfile.telehealth_enabled.is_(telehealth_enabled))
        query = (
            select(User, ProfessionalProfile)
            .join(ProfessionalProfile, ProfessionalProfile.user_id == User.id)
            .where(*filters)
            .order_by(User.name.asc())
            .offset(offset)
            .limit(limit)
        )
        count_query = (
            select(func.count())
            .select_from(User)
            .join(ProfessionalProfile, ProfessionalProfile.user_id == User.id)
            .where(*filters)
        )
        return list(self.session.execute(query).all()), self.session.scalar(count_query) or 0

    def get_professional(self, professional_id: UUID) -> tuple[User, ProfessionalProfile] | None:
        query = (
            select(User, ProfessionalProfile)
            .join(ProfessionalProfile, ProfessionalProfile.user_id == User.id)
            .where(
                User.id == professional_id,
                User.role == UserRole.PROFESSIONAL,
                User.is_active.is_(True),
            )
        )
        return self.session.execute(query).first()

    def has_patient_assignment(self, professional_id: UUID, patient_id: UUID) -> bool:
        query = select(ProfessionalPatient.professional_id).where(
            ProfessionalPatient.professional_id == professional_id,
            ProfessionalPatient.patient_id == patient_id,
        )
        return self.session.scalar(query) is not None