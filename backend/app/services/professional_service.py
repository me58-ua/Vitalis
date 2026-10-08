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
                    gender=user.gender,
                    email=user.email,
                    tel=user.tel,
                    blood_type=profile.blood_type,
                    allergies_summary=profile.allergies_summary,
                    chronic_conditions_summary=profile.chronic_conditions_summary,
                )
                for user, profile in records
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
    ) -> ProfessionalListResponse:
        records, total = self.professionals.list_professionals(
            name=name,
            specialty=specialty,
            is_accepting_new_patients=is_accepting_new_patients,
            telehealth_enabled=telehealth_enabled,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return ProfessionalListResponse(
            professionals=[self._public_response(user, profile) for user, profile in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_professional(self, professional_id) -> ProfessionalPublicResponse:
        record = self.professionals.get_professional(professional_id)
        if record is None:
            raise ProfessionalNotFoundError("Professional not found")
        return self._public_response(*record)

    @staticmethod
    def _public_response(user, profile) -> ProfessionalPublicResponse:
        return ProfessionalPublicResponse(
            id=user.id,
            name=user.name,
            specialty=profile.specialty,
            bio=profile.bio,
            practice_address=profile.practice_address,
            practice_phone=profile.practice_phone,
            is_accepting_new_patients=profile.is_accepting_new_patients,
            default_consultation_duration_minutes=profile.default_consultation_duration_minutes,
            telehealth_enabled=profile.telehealth_enabled,
            license_number=profile.license_number,
        )