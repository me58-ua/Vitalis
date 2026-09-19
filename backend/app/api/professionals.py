from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_current_professional,
    get_professional_repository,
)
from app.models import User
from app.repositories.professional_repository import ProfessionalRepository
from app.schemas.profiles import (
    PatientListResponse,
    PatientSummaryResponse,
    ProfessionalListResponse,
    ProfessionalPublicResponse,
)


router = APIRouter(tags=["professionals"])
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Professionals = Annotated[ProfessionalRepository, Depends(get_professional_repository)]


def professional_response(user: User, profile) -> ProfessionalPublicResponse:
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
    )


@router.get("/professionals/me/patients", response_model=PatientListResponse)
def list_my_patients(
    current_user: CurrentProfessional,
    professionals: Professionals,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PatientListResponse:
    patient_records, total = professionals.list_patients(
        professional_id=current_user.id,
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
            for user, profile in patient_records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/professionals", response_model=ProfessionalListResponse)
def list_professionals(
    professionals: Professionals,
    name: str | None = Query(default=None, max_length=100),
    specialty: str | None = Query(default=None, max_length=150),
    is_accepting_new_patients: bool | None = None,
    telehealth_enabled: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProfessionalListResponse:
    records, total = professionals.list_professionals(
        name=name,
        specialty=specialty,
        is_accepting_new_patients=is_accepting_new_patients,
        telehealth_enabled=telehealth_enabled,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return ProfessionalListResponse(
        professionals=[professional_response(user, profile) for user, profile in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/professionals/{professional_id}", response_model=ProfessionalPublicResponse)
def get_professional(professional_id: UUID, professionals: Professionals) -> ProfessionalPublicResponse:
    record = professionals.get_professional(professional_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
    return professional_response(*record)