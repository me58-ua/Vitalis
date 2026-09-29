import json
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.models import Allergy, ChronicCondition, HabitLog, Medication
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository


class PatientHistoryAccessError(Exception):
    pass


class PatientHealthService:
    blocks = ("alergias", "enfermedades_cronicas", "medicacion", "habitos")

    def __init__(
        self,
        profiles: ProfileRepository,
        appointments: AppointmentRepository | None = None,
        prescriptions: PrescriptionRepository | None = None,
    ):
        self.profiles = profiles
        self.appointments = appointments
        self.prescriptions = prescriptions

    def snapshot(self, profile, professional_id=None):
        if self.appointments is None or self.prescriptions is None or professional_id is None:
            if not profile.share_health_data:
                return {"consent_shared": False, "message": "El paciente no ha compartido sus datos de salud."}
            return {"consent_shared": True, **self.profiles.list_health_records(profile.id)}

        if not self.appointments.has_shared_appointment(profile.user_id, professional_id):
            raise PatientHistoryAccessError("No shared appointment with this patient")
        professional_profile = self.profiles.get_professional(professional_id)
        if professional_profile is None:
            raise PatientHistoryAccessError("Professional profile not found")

        if profile.share_health_data:
            result = {"consent_shared": True, **self.profiles.list_health_records(profile.id)}
        else:
            result = {"consent_shared": False, "message": "El paciente no ha compartido sus datos de salud."}
        result.update(
            appointments=self.appointments.list_patient_history(profile.user_id, professional_id),
            clinical_notes=self.appointments.list_patient_notes(profile.user_id, professional_id),
            prescriptions=self.prescriptions.list_for_patient_and_professional(profile.id, professional_profile.id),
        )
        return result

    def snapshot_by_user_id(self, user_id, professional_id=None):
        profile = self.profiles.get_patient(user_id)
        if profile is None:
            raise ValueError("Profile not found")
        return self.snapshot(profile, professional_id)

    def save_onboarding_message(self, profile, block: str, message: str):
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
            return "Onboarding completado. Puedes actualizar tus datos desde tu perfil."
        return {
            "alergias": "¿Tienes alguna enfermedad crónica?",
            "enfermedades_cronicas": "¿Tomas actualmente alguna medicación?",
            "medicacion": "¿Quieres registrar algún hábito de sueño, ejercicio, dieta, tabaco o alcohol?",
            "habitos": "¿Tienes algún otro dato de salud que quieras registrar?",
        }[block]