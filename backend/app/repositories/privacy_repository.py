from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import Allergy, ChronicCondition, HabitLog, HealthDocument, Medication, PatientProfile, User
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken


class PrivacyRepository:
    def __init__(self, session: Session):
        self.session = session

    def erase_patient_health(self, patient_id: UUID) -> list[str]:
        documents = list(
            self.session.scalars(select(HealthDocument).where(HealthDocument.patient_id == patient_id))
        )
        for model in (Allergy, ChronicCondition, Medication, HabitLog, HealthDocument):
            self.session.execute(delete(model).where(model.patient_id == patient_id))
        self.session.flush()
        return [document.file_url for document in documents]

    def anonymize_patient_profile(self, profile: PatientProfile) -> None:
        profile.address = None
        profile.blood_type = None
        profile.onboarding_completed = False
        profile.share_health_data = False
        self.session.flush()

    def anonymize_professional_profile(self, profile) -> None:
        profile.specialty = "Cuenta eliminada"
        profile.bio = None
        profile.practice_address = None
        profile.practice_phone = None
        profile.license_number = f"deleted-{profile.user_id.hex[:12]}"
        profile.is_accepting_new_patients = False
        profile.telehealth_enabled = False
        self.session.flush()

    def revoke_user_sessions(self, user_id: UUID) -> None:
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        self.session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=func.now())
        )
        self.session.flush()

    def anonymize_user(self, user: User) -> None:
        suffix = user.id.hex[:12]
        user.name = "Cuenta eliminada"
        user.dni = f"deleted-{suffix}"
        user.username = f"deleted-{suffix}"
        user.email = f"deleted-{suffix}@invalid.local"
        user.tel = "deleted"
        user.gender = None
        user.password_hash = "!account-erased!"
        user.is_active = False
        user.terms_accepted = False
        user.session_version += 1
        self.session.flush()