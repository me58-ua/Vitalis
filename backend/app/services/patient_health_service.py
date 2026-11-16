from app.ai.onboarding.legacy_service import LegacyOnboardingMixin
# Servicio de salud del paciente: historial autorizado y onboarding estructurado.

from app.models import AuditAction, UserRole
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.audit_service import AuditService
from app.services.family_history_status import family_history_status


class PatientHistoryAccessError(Exception):
    pass


class PatientHealthService(LegacyOnboardingMixin):
    blocks = (
        "alergias",
        "enfermedades_cronicas",
        "medicacion",
        "cuerpo",
        "alcohol",
        "habitos",
        "antecedentes_familiares",
    )

    def __init__(
        self,
        profiles: ProfileRepository,
        appointments: AppointmentRepository | None = None,
        prescriptions: PrescriptionRepository | None = None,
        audits: AuditRepository | None = None,
        llm_client=None,
        risk_service=None,
        family_history_service=None,
        health_documents=None,
    ):
        self.profiles = profiles
        self.appointments = appointments
        self.prescriptions = prescriptions
        self.audit = AuditService(audits)
        self.llm_client = llm_client
        self.risk_service = risk_service
        self.family_history_service = family_history_service
        self.health_documents = health_documents

    def snapshot(self, profile, professional_id=None):
        if self.appointments is None or self.prescriptions is None or professional_id is None:
            if not profile.share_health_data:
                return {"consent_shared": False, "message_code": "HEALTH_DATA_NOT_SHARED"}
            result = {"consent_shared": True, **self.profiles.list_health_records(profile.id)}
            result['family_history_status'] = family_history_status(profile, result.get('family_history_entries', []))
            if self.health_documents is not None:
                result["health_documents"] = self.health_documents.list_for_patient(profile.id)
            return result

        if not self.appointments.has_shared_appointment(profile.user_id, professional_id):
            raise PatientHistoryAccessError("No shared appointment with this patient")
        professional_profile = self.profiles.get_professional(professional_id)
        if professional_profile is None:
            raise PatientHistoryAccessError("Professional profile not found")

        if profile.share_health_data:
            records = self.profiles.list_health_records(profile.id)
            result = {
                "consent_shared": True,
                "height_cm": getattr(profile, "height_cm", None),
                "weight_kg": getattr(profile, "weight_kg", None),
                "sex_at_birth": getattr(profile, "sex_at_birth", None),
                **records,
                "alcohol_logs": self.profiles.list_alcohol_logs(profile.id)
                if hasattr(self.profiles, "list_alcohol_logs") else [],
                "family_history_entries": records.get("family_history_entries", []),
                "family_history_status": family_history_status(profile, records.get('family_history_entries', [])),
            }
            if self.health_documents is not None:
                result["health_documents"] = self.health_documents.list_for_patient(profile.id)
            self.audit.record(
                professional_id, UserRole.PROFESSIONAL, AuditAction.READ,
                "alcohol_log", profile.id, profile.user_id,
            )
            self.audit.record(
                professional_id, UserRole.PROFESSIONAL, AuditAction.READ,
                "family_history_entry", profile.id, profile.user_id,
            )
        else:
            result = {"consent_shared": False, "message_code": "HEALTH_DATA_NOT_SHARED"}
        result.update(
            appointments=self.appointments.list_patient_history(profile.user_id, professional_id),
            clinical_notes=self.appointments.list_patient_notes(profile.user_id, professional_id),
            prescriptions=self.prescriptions.list_for_patient_and_professional(
                profile.id, professional_profile.id
            ),
        )
        self.audit.record(
            professional_id, UserRole.PROFESSIONAL, AuditAction.READ,
            "patient_profile", profile.id, profile.user_id,
        )
        return result

    def snapshot_by_user_id(self, user_id, professional_id=None):
        profile = self.profiles.get_patient(user_id)
        if profile is None:
            raise ValueError("Profile not found")
        return self.snapshot(profile, professional_id)
