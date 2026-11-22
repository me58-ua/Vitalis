# Servicio profesional: consulta perfiles profesionales y pacientes para mostrar listados y resúmenes públicos.
from app.repositories.professional_repository import ProfessionalRepository
from app.schemas.profiles import (
    PatientListResponse,
    PatientSummaryResponse,
    ProfessionalListResponse,
    ProfessionalPublicResponse,
)


class ProfessionalNotFoundError(Exception):
    pass


class ProfessionalService:
    def __init__(self, professionals: ProfessionalRepository):
        self.professionals = professionals

    def list_my_patients(
        self,
        professional_id,
        search: str | None,
        page: int,
        page_size: int,
    ) -> PatientListResponse:
        records, total = self.professionals.list_patients(
            professional_id=professional_id,
            search=search,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return PatientListResponse(
            patients=[
                PatientSummaryResponse(
                    id=user.id,
                    name=user.name,
                    username=user.username,
                    gender=user.gender if scope in ("basic", "full") else None,
                    email=user.email,
                    tel=user.tel,
                    blood_type=profile.blood_type if scope == "full" else None,
                    allergies_summary=(", ".join(item.name for item in profile.allergies) or None)
                    if scope == "full" else None,
                    chronic_conditions_summary=(", ".join(item.condition_name for item in profile.chronic_conditions) or None)
                    if scope == "full" else None,
                )
                for user, profile, scope in records
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_professionals(
        self,
        name: str | None,
        specialty: str | None,
        is_accepting_new_patients: bool | None,
        telehealth_enabled: bool | None,
        page: int,
        page_size: int,
        appointment_type: str | None = None,
    ) -> ProfessionalListResponse:
        records, total = self.professionals.list_professionals(
            name=name,
            specialty=specialty,
            is_accepting_new_patients=is_accepting_new_patients,
            telehealth_enabled=telehealth_enabled,
            offset=(page - 1) * page_size,
            limit=page_size,
            appointment_type=appointment_type,
        )
        modalities = self.professionals.appointment_modalities([user.id for user, _ in records])
        return ProfessionalListResponse(
            professionals=[self._public_response(user, profile, modalities.get(user.id, set())) for user, profile in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_professional(self, professional_id) -> ProfessionalPublicResponse:
        record = self.professionals.get_professional(professional_id)
        if record is None:
            raise ProfessionalNotFoundError("Professional not found")
        modalities = self.professionals.appointment_modalities([professional_id])
        return self._public_response(*record, modalities.get(professional_id, set()))

    @staticmethod
    def _public_response(user, profile, modalities: set[str]) -> ProfessionalPublicResponse:
        return ProfessionalPublicResponse(
            id=user.id,
            name=user.name,
            specialty=profile.specialty,
            photo_url=getattr(user, "photo_url", None),
            years_experience=getattr(profile, "years_experience", None),
            languages=getattr(profile, "languages", None) or [],
            bio=profile.bio,
            practice_address=profile.practice_address,
            practice_phone=profile.practice_phone,
            is_accepting_new_patients=profile.is_accepting_new_patients,
            default_consultation_duration_minutes=profile.default_consultation_duration_minutes,
            telehealth_enabled=profile.telehealth_enabled,
            appointment_modalities=[
                modality for modality in ("in_person", "video")
                if modality in modalities and (modality != "video" or profile.telehealth_enabled)
            ],
            license_number=profile.license_number,
        )
