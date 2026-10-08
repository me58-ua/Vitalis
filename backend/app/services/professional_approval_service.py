# Servicio de aprobación profesional: lista solicitudes pendientes y decide su aprobación o rechazo.
from datetime import datetime, timezone

from app.models import ProfessionalApprovalStatus, User
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository
from app.models import AuditAction
from app.services.audit_service import AuditService


class ProfessionalApprovalError(Exception):
    pass


class ProfessionalApprovalService:
    def __init__(self, professionals: ProfessionalRepository, users: UserRepository, audits: AuditRepository | None = None):
        self.professionals = professionals
        self.users = users
        self.audit = AuditService(audits)

    def list_pending(self):
        return self.professionals.list_pending_profiles()

    def decide(self, professional_id, admin: User, status: ProfessionalApprovalStatus, reason: str | None = None):
        profile = self.professionals.get_profile_by_user_id(professional_id)
        if profile is None:
            raise ProfessionalApprovalError("Professional not found")
        if status == ProfessionalApprovalStatus.REJECTED and not reason:
            raise ProfessionalApprovalError("A rejection reason is required")

        user = self.users.get_by_id(professional_id)
        if user is None or user.role.value != "professional":
            raise ProfessionalApprovalError("Professional not found")

        profile.approval_status = status
        profile.rejection_reason = reason if status == ProfessionalApprovalStatus.REJECTED else None
        profile.reviewed_at = datetime.now(timezone.utc)
        profile.reviewed_by = admin.id
        user.is_active = status == ProfessionalApprovalStatus.APPROVED
        self.professionals.session.flush()
        self.audit.record(
            admin.id,
            admin.role,
            AuditAction.UPDATE,
            "professional_profile",
            getattr(profile, "id", professional_id),
        )
        return profile