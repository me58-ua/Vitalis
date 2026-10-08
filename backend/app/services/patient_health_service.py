# Servicio de salud del paciente: recopila, guarda y actualiza información clínica y del onboarding.
import json
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.models import Allergy, ChronicCondition, HabitLog, Medication
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.audit_repository import AuditRepository
from app.models import AuditAction, UserRole
from app.services.audit_service import AuditService


class PatientHistoryAccessError(Exception):
    pass


class PatientHealthService:
    blocks = ("alergias", "enfermedades_cronicas", "medicacion", "habitos")

    def __init__(
        self,
        profiles: ProfileRepository,
        appointments: AppointmentRepository | None = None,
        prescriptions: PrescriptionRepository | None = None,
        audits: AuditRepository | None = None,
    ):
        self.profiles = profiles
        self.appointments = appointments
        self.prescriptions = prescriptions
        self.audit = AuditService(audits)

    def snapshot(self, profile, professional_id=None):
        if self.appointments is None or self.prescriptions is None or professional_id is None:
            if not profile.share_health_data:
                return {"consent_shared": False, "message_code": "HEALTH_DATA_NOT_SHARED"}
            return {"consent_shared": True, **self.profiles.list_health_records(profile.id)}

        if not self.appointments.has_shared_appointment(profile.user_id, professional_id):
            raise PatientHistoryAccessError("No shared appointment with this patient")
        professional_profile = self.profiles.get_professional(professional_id)
        if professional_profile is None:
            raise PatientHistoryAccessError("Professional profile not found")

        if profile.share_health_data:
            result = {"consent_shared": True, **self.profiles.list_health_records(profile.id)}
        else:
            result = {"consent_shared": False, "message_code": "HEALTH_DATA_NOT_SHARED"}
        result.update(
            appointments=self.appointments.list_patient_history(profile.user_id, professional_id),
            clinical_notes=self.appointments.list_patient_notes(profile.user_id, professional_id),
            prescriptions=self.prescriptions.list_for_patient_and_professional(profile.id, professional_profile.id),
        )
        self.audit.record(
            professional_id,
            UserRole.PROFESSIONAL,
            AuditAction.READ,
            "patient_profile",
            profile.id,
            profile.id,
        )
        return result

    def snapshot_by_user_id(self, user_id, professional_id=None):
        profile = self.profiles.get_patient(user_id)
        if profile is None:
            raise ValueError("Profile not found")
        return self.snapshot(profile, professional_id)

    def save_onboarding_message(self, profile, block: str, message: str):
        if getattr(profile, "ai_processing_consent", True) is False:
            self.skip(profile)
            return True, False, "AI_CONSENT_REQUIRED"
        if block not in self.blocks:
            raise ValueError("Invalid onboarding block")
        extracted = self._extract(message, block)
        saved = False
        for item in extracted:
            model = {
                "alergias": Allergy,
                "enfermedades_cronicas": ChronicCondition,
                "medicacion": Medication,
                "habitos": HabitLog,
            }[block]
            self.profiles.add_health_record(model(patient_id=profile.id, **item))
            saved = True
        next_index = self.blocks.index(block) + 1
        completed = next_index >= len(self.blocks)
        profile.onboarding_completed = completed
        self.profiles.session.flush()
        return completed, saved, self._next_question(block, completed)

    def skip(self, profile):
        profile.onboarding_completed = True
        self.profiles.session.flush()
        return True

    def resume(self, profile) -> bool:
        if getattr(profile, "ai_processing_consent", True) is False:
            profile.onboarding_completed = True
            self.profiles.session.flush()
            return False
        profile.onboarding_completed = False
        self.profiles.session.flush()
        return True

    def _extract(self, message: str, block: str) -> list[dict]:
        if settings.AI_API_URL:
            try:
                request = Request(
                    settings.AI_API_URL,
                    data=json.dumps({"block": block, "message": message}).encode(),
                    headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {settings.AI_API_KEY}"} if settings.AI_API_KEY else {})},
                    method="POST",
                )
                with urlopen(request, timeout=8) as response:
                    payload = json.loads(response.read())
                if isinstance(payload, list):
                    return payload
                if isinstance(payload, dict) and isinstance(payload.get("records"), list):
                    return payload["records"]
            except (OSError, URLError, ValueError, json.JSONDecodeError):
                pass
        return self._fallback_extract(message, block)

    def _fallback_extract(self, message: str, block: str) -> list[dict]:
        value = message.strip()
        if not value or value.lower() in {"no", "ninguna", "ninguno", "no tengo"}:
            return []
        if block == "alergias":
            return [{"name": value[:150], "severity": "leve"}]
        if block == "enfermedades_cronicas":
            return [{"condition_name": value[:200], "active": True}]
        if block == "medicacion":
            return [{"name": value[:200], "dosage": "no indicado", "frequency": "no indicada", "active": True}]
        return [{"habit_type": "dieta", "value": None, "unit": value[:50], "date": datetime.now(timezone.utc).date()}]

    def _next_question(self, block: str, completed: bool) -> str:
        if completed:
            return "ONBOARDING_COMPLETED"
        return {
            "alergias": "ONBOARDING_NEXT_CHRONIC_CONDITION",
            "enfermedades_cronicas": "ONBOARDING_NEXT_MEDICATION",
            "medicacion": "ONBOARDING_NEXT_HABIT",
            "habitos": "ONBOARDING_NEXT_OTHER",
        }[block]