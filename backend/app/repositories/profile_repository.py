from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlcoholLog, Allergy, ChronicCondition, HabitLog, Medication, PatientProfile, ProfessionalProfile


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

    def add_health_record(self, record):
        self.session.add(record)
        self.session.flush()
        return record

    def list_health_records(self, profile_id):
        return {
            "allergies": list(self.session.scalars(select(Allergy).where(Allergy.patient_id == profile_id).order_by(Allergy.id))),
            "chronic_conditions": list(self.session.scalars(select(ChronicCondition).where(ChronicCondition.patient_id == profile_id).order_by(ChronicCondition.id))),
            "medications": list(self.session.scalars(select(Medication).where(Medication.patient_id == profile_id).order_by(Medication.id))),
            "habit_logs": list(self.session.scalars(select(HabitLog).where(HabitLog.patient_id == profile_id).order_by(HabitLog.date, HabitLog.id))),
        }

    def get_health_record(self, model, profile_id, record_id):
        return self.session.scalar(select(model).where(model.patient_id == profile_id, model.id == record_id))

    def list_alcohol_logs(self, profile_id, limit=100):
        return list(self.session.scalars(
            select(AlcoholLog).where(AlcoholLog.patient_id == profile_id)
            .order_by(AlcoholLog.date.desc(), AlcoholLog.id.desc()).limit(limit)
        ))

    def delete_health_record(self, record):
        self.session.delete(record)
        self.session.flush()