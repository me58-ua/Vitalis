from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.models import AuditAction, ProfessionalApprovalStatus
from app.schemas.profiles import ProfessionalProfileUpdate
from app.services.audit_service import AuditService
from app.services.profile_service import ProfileNotFoundError


class ProfileChangeConflict(Exception):
    pass


class ProfileChangeValidation(Exception):
    pass


class ProfileChangeService:
    def __init__(self, profiles, audits=None):
        self.profiles = profiles
        self.audit = AuditService(audits)

    def submit(self, user, data):
        profile = self._locked(user.id)
        if profile.approval_status != ProfessionalApprovalStatus.APPROVED:
            raise ProfileChangeValidation("PROFESSIONAL_APPROVAL_REQUIRED")
        changes = {name: value for name, value in data.model_dump(exclude_unset=True).items()
                   if value != getattr(profile, name)}
        if not changes:
            raise ProfileChangeValidation("PROFILE_CHANGE_EMPTY")
        profile.pending_changes = changes
        profile.change_request_id = uuid4()
        profile.change_status = "pending"
        profile.change_requested_at = datetime.now(timezone.utc)
        profile.change_reviewed_at = None
        profile.change_reviewed_by = None
        profile.change_rejection_reason = None
        self.profiles.session.flush()
        self.audit.record(user.id, user.role, AuditAction.UPDATE, "professional_profile_change", profile.id)
        return profile

    def decide(self, professional_id, admin, decision, approve):
        profile = self._locked(professional_id)
        if profile.change_status != "pending" or profile.change_request_id != decision.request_id:
            raise ProfileChangeConflict("PROFILE_CHANGE_STALE")
        if not approve and not decision.reason:
            raise ProfileChangeValidation("PROFILE_CHANGE_REASON_REQUIRED")
        if approve:
            # Revalidate the stored allowlist; never apply arbitrary JSON keys.
            changes = ProfessionalProfileUpdate.model_validate(profile.pending_changes)
            for name, value in changes.model_dump(exclude_unset=True).items():
                setattr(profile, name, value)
        profile.change_status = "approved" if approve else "rejected"
        profile.change_reviewed_at = datetime.now(timezone.utc)
        profile.change_reviewed_by = admin.id
        profile.change_rejection_reason = None if approve else decision.reason
        profile.pending_changes = None if approve else profile.pending_changes
        try:
            self.profiles.session.flush()
        except IntegrityError as error:
            self.profiles.session.rollback()
            raise ProfileChangeConflict("PROFILE_CHANGE_IDENTIFIER_CONFLICT") from error
        self.audit.record(admin.id, admin.role, AuditAction.UPDATE, "professional_profile_change", profile.id)
        # Approval of an edit does not reactivate an administratively disabled account.
        return profile

    def _locked(self, professional_id):
        profile = self.profiles.lock_professional(professional_id)
        if profile is None:
            raise ProfileNotFoundError("Professional profile not found")
        return profile
