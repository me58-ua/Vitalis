from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PatientProfile, ProfessionalProfile


class ProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_patient(self, user_id: UUID) -> PatientProfile | None:
        return self.session.scalar(select(PatientProfile).where(PatientProfile.user_id == user_id))

    def get_professional(self, user_id: UUID) -> ProfessionalProfile | None:
        return self.session.scalar(
            select(ProfessionalProfile).where(ProfessionalProfile.user_id == user_id)
        )

    def update(self, profile: PatientProfile | ProfessionalProfile, values: dict):
        for field, value in values.items():
            setattr(profile, field, value)
        self.session.flush()
        return profile