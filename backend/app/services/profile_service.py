from datetime import datetime, timezone

# Servicio de perfiles: actualiza datos básicos, contraseñas y perfiles de pacientes o profesionales.
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.profiles import (
    BasicUserUpdate,
    ChangePasswordRequest,
    PatientProfileUpdate,
    ProfessionalProfileUpdate,
)


class InvalidCurrentPasswordError(Exception):
    pass


class ProfileNotFoundError(Exception):
    pass


class ProfileService:
    def __init__(self, users: UserRepository, profiles: ProfileRepository):
        self.users = users
        self.profiles = profiles

    def update_basic_user(self, user: User, data: BasicUserUpdate) -> User:
        return self.users.update(user, data.model_dump(exclude_unset=True))

    def change_password(self, user: User, data: ChangePasswordRequest) -> User:
        if not verify_password(data.current_password, user.password_hash):
            raise InvalidCurrentPasswordError
        user.password_hash = hash_password(data.new_password)
        user.session_version += 1
        self.users.session.flush()
        return user

    def get_patient_profile(self, user: User):
        profile = self.profiles.get_patient(user.id)
        if profile is None:
            raise ProfileNotFoundError("Profile not found")
        return self.patient_profile_response(profile)

    def get_professional_profile(self, user: User):
        profile = self.profiles.get_professional(user.id)
        if profile is None:
            raise ProfileNotFoundError("Profile not found")
        return profile

    def update_patient_profile(self, user: User, data: PatientProfileUpdate):
        profile = self.get_patient_profile(user)
        return self.patient_profile_response(
            self.profiles.update(profile, data.model_dump(exclude_unset=True))
        )

    def update_ai_consent(self, user: User, enabled: bool):
        profile = self.profiles.get_patient(user.id)
        if profile is None:
            raise ProfileNotFoundError("Profile not found")
        profile.ai_processing_consent = enabled
        profile.ai_processing_consent_at = datetime.now(timezone.utc)
        self.profiles.session.flush()
        return self.patient_profile_response(profile)

    @staticmethod
    def patient_profile_response(profile):
        consent = getattr(profile, "ai_processing_consent", False)
        profile.ai_processing_consent = consent
        profile.ai_consent_required = not consent
        profile.ai_consent_code = "AI_CONSENT_REQUIRED" if not consent else None
        return profile

    def update_professional_profile(self, user: User, data: ProfessionalProfileUpdate, audits=None):
        from app.services.profile_change_service import ProfileChangeService
        return ProfileChangeService(self.profiles, audits).submit(user, data)
