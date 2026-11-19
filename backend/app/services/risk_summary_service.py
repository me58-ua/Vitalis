from uuid import UUID

from app.models import PatientProfile, User, UserRole
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.risk_snapshot_repository import RiskSnapshotRepository
from app.services.audit_service import AuditService
from app.services.risk_service import (
    AUDIT_C_SOURCE, FAMILY_SOURCE, OMS_SOURCE, TOBACCO_SOURCE,
    RiskService, calc_trend, FAMILY_GUIDANCE,
)
from app.models import AuditAction
from app.repositories.audit_repository import AuditRepository


SOURCES = {
    "who": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
    "audit_c": "https://pubmed.ncbi.nlm.nih.gov/9698702/",
    "tobacco": "https://www.who.int/initiatives/mpower",
    "family_history": FAMILY_SOURCE,
    "diabetes": "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/type-2-diabetes",
    "cancer": "https://www.cdc.gov/cancer/risk-factors/family-health-history.html",
    "cardiovascular": "https://www.cdc.gov/heart-disease-family-history/about/",
    "huntington": "https://medlineplus.gov/genetics/condition/huntingtons-disease/",
    **{category: source for category, (_, source) in FAMILY_GUIDANCE.items()},
}


class RiskSummaryAccessError(Exception):
    pass


class RiskSummaryService:
    def __init__(
        self,
        risk: RiskService,
        snapshots: RiskSnapshotRepository,
        profiles: ProfileRepository,
        appointments: AppointmentRepository | None = None,
        audits: AuditRepository | None = None,
    ):
        self.risk = risk
        self.snapshots = snapshots
        self.profiles = profiles
        self.appointments = appointments
        self.audit = AuditService(audits)

    def get(self, patient_id: UUID, current_user: User) -> dict:
        profile = self.profiles.session.get(PatientProfile, patient_id)
        if profile is None:
            raise RiskSummaryAccessError("Patient profile not found")
        owner = current_user.role == UserRole.PATIENT and profile.user_id == current_user.id
        professional = current_user.role == UserRole.PROFESSIONAL
        if not owner and not professional:
            raise RiskSummaryAccessError("Not authorized to access risk summary")
        if professional:
            if self.appointments is None or not self.appointments.has_shared_appointment(
                profile.user_id, current_user.id
            ):
                raise RiskSummaryAccessError("No shared appointment with this patient")
            if self.appointments.health_sharing_scope(profile, current_user.id) != "full":
                raise RiskSummaryAccessError("The patient has not shared health data")
            self.audit.record(
                current_user.id, UserRole.PROFESSIONAL, AuditAction.READ,
                "risk_assessment", patient_id, profile.user_id,
            )
            if not profile.ai_processing_consent:
                return {"results": [], "ai_consent_required": False, "sources": SOURCES}
        elif not profile.ai_processing_consent:
            return {
                "results": [], "ai_consent_required": True,
                "message_code": "AI_CONSENT_REQUIRED", "sources": SOURCES,
            }

        results = self.risk.evaluate(patient_id)
        summary = []
        for result in results:
            history, _ = self.snapshots.list_history(patient_id, result.model, limit=100)
            summary.append({
                **result.model_dump(),
                "trend": calc_trend(result.model, history),
            })
        return {"results": summary, "sources": SOURCES}
