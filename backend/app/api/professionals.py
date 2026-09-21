from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_appointment_repository,
    get_current_professional,
    get_professional_repository,
    get_user_repository,
)
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointments import (
    AppointmentCancelRequest,
    ConsultationNoteCreate,
    ConsultationNoteResponse,
    ConsultationNoteUpdate,
    ProfessionalAppointmentCreate,
    ProfessionalAppointmentStatusUpdate,
    ProfessionalScheduleResponse,
    ProfessionalScheduleUpdate,
    AppointmentResponse,
)
from app.schemas.profiles import PatientListResponse, ProfessionalListResponse, ProfessionalPublicResponse
from app.services.appointment_service import (
    AppointmentAccessError,
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentService,
    AppointmentValidationError,
)
from app.services.professional_service import ProfessionalNotFoundError, ProfessionalService


router = APIRouter(tags=["professionals"])
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Professionals = Annotated[ProfessionalRepository, Depends(get_professional_repository)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Users = Annotated[UserRepository, Depends(get_user_repository)]


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


@router.post(
    "/professionals/{professional_id}/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_professional_appointment(
    professional_id: UUID,
    data: ProfessionalAppointmentCreate,
    current_user: CurrentProfessional,
    appointments: Appointments,
    users: Users,
    professionals: Professionals,
):
    try:
        return AppointmentService(appointments, users, professionals).create_for_professional(
            professional_id, current_user, data
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/professionals/{professional_id}/consultation-notes",
    response_model=ConsultationNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_consultation_note(
    professional_id: UUID,
    data: ConsultationNoteCreate,
    current_user: CurrentProfessional,
    appointments: Appointments,
    users: Users,
):
    try:
        return AppointmentService(appointments, users).create_consultation_note(
            professional_id, current_user, data
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch(
    "/professionals/{professional_id}/appointments/{appointment_id}/status",
    response_model=AppointmentResponse,
)
def update_professional_appointment_status(
    professional_id: UUID,
    appointment_id: UUID,
    data: ProfessionalAppointmentStatusUpdate,
    current_user: CurrentProfessional,
    appointments: Appointments,
    users: Users,
):
    try:
        return AppointmentService(appointments, users).update_status_as_professional(
            professional_id, current_user, appointment_id, data
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch(
    "/professionals/{professional_id}/schedules/{schedule_id}",
    response_model=ProfessionalScheduleResponse,
)
def update_professional_schedule(
    professional_id: UUID,
    schedule_id: UUID,
    data: ProfessionalScheduleUpdate,
    current_user: CurrentProfessional,
    appointments: Appointments,
    users: Users,
):
    try:
        return AppointmentService(appointments, users).update_schedule_as_professional(
            professional_id, current_user, schedule_id, data
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch(
    "/professionals/{professional_id}/consultation-notes/{note_id}",
    response_model=ConsultationNoteResponse,
)
def update_professional_consultation_note(
    professional_id: UUID,
    note_id: UUID,
    data: ConsultationNoteUpdate,
    current_user: CurrentProfessional,
    appointments: Appointments,
    users: Users,
):
    try:
        return AppointmentService(appointments, users).update_consultation_note(
            professional_id, current_user, note_id, data
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/professionals/{professional_id}/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
def cancel_professional_appointment(
    professional_id: UUID,
    appointment_id: UUID,
    data: AppointmentCancelRequest,
    current_user: CurrentProfessional,
    appointments: Appointments,
    users: Users,
):
    try:
        return AppointmentService(appointments, users).cancel_appointment(
            professional_id,
            appointment_id,
            current_user,
            data,
            enforce_patient_notice=False,
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error