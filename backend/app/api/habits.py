from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_appointment_repository,
    get_current_patient,
    get_current_professional,
    get_profile_repository,
)
from app.models import HabitType, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.habit_repository import HabitRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.habits import HabitHistoryListResponse
from app.services.habit_service import HabitAccessError, HabitService, HabitValidationError
from app.database import get_db
from sqlalchemy.orm import Session


router = APIRouter(tags=["habits"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
DbSession = Annotated[Session, Depends(get_db)]


def _service(db: Session, profiles: ProfileRepository, appointments: AppointmentRepository) -> HabitService:
    return HabitService(HabitRepository(db), profiles, appointments)


def _query_params(
    habit_type: HabitType | None = None,
    search: str | None = Query(default=None, min_length=1, max_length=50),
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return habit_type, search, start_date, end_date, page, page_size


@router.get("/patients/me/health/habits", response_model=HabitHistoryListResponse)
def list_my_habits(
    current_user: CurrentPatient,
    profiles: Profiles,
    appointments: Appointments,
    db: DbSession,
    params: tuple = Depends(_query_params),
):
    try:
        return _service(db, profiles, appointments).list_for_patient(current_user, *params)
    except HabitValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.get("/professionals/{professional_id}/patients/{patient_id}/health/habits", response_model=HabitHistoryListResponse)
def list_patient_habits(
    professional_id: UUID,
    patient_id: UUID,
    current_user: CurrentProfessional,
    profiles: Profiles,
    appointments: Appointments,
    db: DbSession,
    params: tuple = Depends(_query_params),
):
    if professional_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Professional identity does not match the URL")
    try:
        return _service(db, profiles, appointments).list_for_professional(patient_id, current_user.id, *params)
    except HabitAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except HabitValidationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error