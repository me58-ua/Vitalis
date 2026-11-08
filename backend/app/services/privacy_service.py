# Servicio de privacidad: elimina la cuenta y sus datos relacionados mediante `erase_account`.
from pathlib import Path

from app.models import AuditAction, User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.privacy_repository import PrivacyRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.audit_service import AuditService
from app.services.file_storage import FileStorage


class PrivacyAccountNotFoundError(Exception):
    pass


class PrivacyService:
    def __init__(
        self,
        privacy: PrivacyRepository,
        profiles: ProfileRepository,
        audits: AuditRepository,
        storage: FileStorage,
    ):
        self.privacy = privacy
        self.profiles = profiles
        self.audit = AuditService(audits)
        self.storage = storage

    def erase_account(self, current_user: User) -> None:
        patient_profile = self.profiles.get_patient(current_user.id)
        professional_profile = self.profiles.get_professional(current_user.id)
        if patient_profile is None and professional_profile is None:
            raise PrivacyAccountNotFoundError("Account profile not found")

        for file_key in self.privacy.erase_spontaneous_chats(current_user.id):
            self.storage.path_for(file_key).unlink(missing_ok=True)

        patient_id = patient_profile.user_id if patient_profile is not None else None
        if patient_profile is not None:
            file_keys = self.privacy.erase_patient_health(patient_profile.id)
            self.privacy.anonymize_patient_profile(patient_profile)
            for file_key in file_keys:
                self.storage.path_for(file_key).unlink(missing_ok=True)
        if professional_profile is not None:
            self.privacy.anonymize_professional_profile(professional_profile)

        self.privacy.revoke_user_sessions(current_user.id)
        self.audit.record(
            current_user.id,
            current_user.role,
            AuditAction.DELETE,
            "user",
            current_user.id,
            patient_id,
        )
        self.privacy.anonymize_user(current_user)
