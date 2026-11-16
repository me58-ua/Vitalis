from datetime import date
from uuid import UUID

from app.models import (
    AuditAction,
    FamilyHistoryEntry,
    FamilyRelationship,
    HereditaryConditions,
    User,
    UserRole,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.family_history_repository import FamilyHistoryRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.audit_service import AuditService


class FamilyHistoryAccessError(Exception):
    pass


class FamilyHistoryNotFoundError(Exception):
    pass


class FamilyHistoryService:
    def __init__(
        self,
        entries: FamilyHistoryRepository,
        profiles: ProfileRepository,
        audits: AuditRepository | None = None,
        risk_service=None,
    ):
        self.entries = entries
        self.profiles = profiles
        self.audit = AuditService(audits)
        self.risk_service = risk_service

    def list_for_patient(self, user: User) -> list[FamilyHistoryEntry]:
        profile = self._owned_profile(user)
        return self.entries.list_for_patient(profile.id)

    def create_from_onboarding(
        self,
        user: User,
        relationship: FamilyRelationship,
        condition_category: HereditaryConditions,
        detail: str | None,
        age_at_diagnosis: int | None,
        recorded_date: date | None = None,
        relative_detail: str | None = None,
        notes: str | None = None,
    ) -> FamilyHistoryEntry:
        profile = self._owned_profile(user)
        if detail is not None and len(detail) > 150:
            raise ValueError("Family history detail cannot exceed 150 characters")
        if relative_detail is not None and len(relative_detail) > 100:
            raise ValueError('Relative detail cannot exceed 100 characters')
        if notes is not None and len(notes) > 500:
            raise ValueError('Family history notes cannot exceed 500 characters')
        if age_at_diagnosis is not None and not 0 <= age_at_diagnosis <= 120:
            raise ValueError("Age at diagnosis must be between 0 and 120")
        entry = self.entries.create(
            FamilyHistoryEntry(
                patient_id=profile.id,
                relationship=relationship,
                condition_category=condition_category,
                detail=detail,
                relative_detail=relative_detail,
                notes=notes,
                age_at_diagnosis=age_at_diagnosis,
                recorded_date=recorded_date or date.today(),
            )
        )
        profile.family_history_reviewed = True
        self.profiles.session.flush()
        self._record_risk(profile.id)
        self.audit.record(user.id, UserRole.PATIENT, AuditAction.CREATE, "family_history_entry", entry.id, profile.user_id)
        return entry

    def declare_none_from_onboarding(self, user: User) -> None:
        profile = self._owned_profile(user)
        profile.family_history_reviewed = True
        self.profiles.session.flush()
        self._record_risk(profile.id)

    def delete_for_patient(self, user: User, entry_id: int) -> None:
        profile = self._owned_profile(user)
        entry = self.entries.get_for_patient(profile.id, entry_id)
        if entry is None:
            raise FamilyHistoryNotFoundError("Family history entry not found")
        self.entries.delete(entry)
        self._record_risk(profile.id)
        self.audit.record(user.id, UserRole.PATIENT, AuditAction.DELETE, "family_history_entry", entry.id, profile.user_id)

    def _owned_profile(self, user: User):
        profile = self.profiles.get_patient(user.id)
        if profile is None:
            raise FamilyHistoryNotFoundError("Profile not found")
        return profile

    def _record_risk(self, patient_id: UUID) -> None:
        if self.risk_service is not None:
            self.risk_service.evaluate_and_record(patient_id, trigger="family_change")
