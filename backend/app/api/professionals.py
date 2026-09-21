from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_current_professional,
    get_professional_repository,
)
from app.models import User
from app.repositories.professional_repository import ProfessionalRepository
from app.schemas.profiles import PatientListResponse, ProfessionalListResponse, ProfessionalPublicResponse
from app.services.professional_service import ProfessionalNotFoundError, ProfessionalService


router = APIRouter(tags=["professionals"])
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Professionals = Annotated[ProfessionalRepository, Depends(get_professional_repository)]


@router.get("/professionals/me/patients", response_model=PatientListResponse)
def list_my_patients(
    current_user: CurrentProfessional,
    professionals: Professionals,
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PatientListResponse:
    return ProfessionalService(professionals).list_my_patients(
        current_user.id, search, page, page_size
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
    return ProfessionalService(professionals).list_professionals(
        name,
        specialty,
        is_accepting_new_patients,
        telehealth_enabled,
        page,
        page_size,
    )


@router.get("/professionals/{professional_id}", response_model=ProfessionalPublicResponse)
def get_professional(professional_id: UUID, professionals: Professionals) -> ProfessionalPublicResponse:
    try:
        return ProfessionalService(professionals).get_professional(professional_id)
    except ProfessionalNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error