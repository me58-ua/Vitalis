from datetime import datetime
from uuid import UUID

from app.models import PatientProfile, User, UserRole
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.risk_snapshot_repository import RiskSnapshotRepository
from app.services.audit_service import AuditService
from app.models import AuditAction
from app.repositories.audit_repository import AuditRepository
from app.services.risk_service import calc_trend


class RiskHistoryAccessError(Exception):
    pass


class RiskHistoryService:
    def __init__(
        self,
        snapshots: RiskSnapshotRepository,
        profiles: ProfileRepository,
        appointments: AppointmentRepository | None = None,
        audits: AuditRepository | None = None,
    ):
        self.snapshots = snapshots
        self.profiles = profiles
        self.appointments = appointments
        self.audit = AuditService(audits)

    def list_for_user(
        self, patient_id: UUID, current_user: User, model: str | None,
        from_date: datetime | None, to_date: datetime | None, cursor: str | None, limit: int,
    ) -> dict:
        profile = self.profiles.session.get(PatientProfile, patient_id)
        if profile is None:
            raise RiskHistoryAccessError("Patient profile not found")
        is_owner = current_user.role == UserRole.PATIENT and profile.user_id == current_user.id
        if not is_owner:
            if current_user.role != UserRole.PROFESSIONAL or self.appointments is None:
                raise RiskHistoryAccessError("Not authorized to access risk history")
            if not profile.share_health_data or not self.appointments.has_shared_appointment(profile.user_id, current_user.id):
                raise RiskHistoryAccessError("Not authorized to access risk history")
            self.audit.record(
                current_user.id, UserRole.PROFESSIONAL, AuditAction.READ,
                "risk_assessment", patient_id, patient_id,
            )
        if not profile.ai_processing_consent:
            return {
                "snapshots": [], "next_cursor": None, "trend": "insufficient_history",
                "ai_consent_required": True, "message_code": "AI_CONSENT_REQUIRED",
            }
        snapshots, next_cursor = self.snapshots.list_history(
            patient_id, model, from_date, to_date, cursor, limit
        )
        trend = "insufficient_history"
        if model:
            trend_rows, _ = self.snapshots.list_history(patient_id, model, from_date, to_date, None, 100)
            trend = calc_trend(model, trend_rows)
        return {"snapshots": snapshots, "next_cursor": next_cursor, "trend": trend}
