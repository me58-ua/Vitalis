from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_appointment_repository,
    get_current_admin,
    get_current_patient,
    get_user_repository,
)
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointments import (
    AdminAppointmentUpdate,
    AppointmentCancelRequest,
    AdminAppointmentCreate,
    AdminAppointmentResponse,
    AdminScheduleCreate,
    AdminScheduleResponse,
)
from app.services.admin_appointment_service import (
    AdminAppointmentConflictError,
    AdminAppointmentNotFoundError,
    AdminAppointmentService,
)
from app.services.appointment_service import (
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentService,
    AppointmentValidationError,
)


router = APIRouter(prefix="/admin", tags=["admin-appointments"])
patient_router = APIRouter(tags=["patient-appointments"])
AdminUser = Annotated[User, Depends(get_current_admin)]
CurrentPatient = Annotated[User, Depends(get_current_patient)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Users = Annotated[UserRepository, Depends(get_user_repository)]


@router.post("/schedules", response_model=AdminScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: AdminScheduleCreate,
    _: AdminUser,
    appointments: Appointments,
    users: Users,
):
    try:
        return AdminAppointmentService(appointments, users).create_schedule(data)
    except AdminAppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AdminAppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/appointments", response_model=AdminAppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    data: AdminAppointmentCreate,
    _: AdminUser,
    appointments: Appointments,
    users: Users,
):
    try:
        return AdminAppointmentService(appointments, users).create_appointment(data)
    except AdminAppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AdminAppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch(
    "/appointments/{appointment_id}",
    response_model=AdminAppointmentResponse,
)
def update_appointment(
    appointment_id: UUID,
    data: AdminAppointmentUpdate,
    current_admin: AdminUser,
    appointments: Appointments,
    users: Users,
):
    try:
        return AppointmentService(appointments, users).update_as_admin(
            appointment_id, data, current_admin
        )
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@patient_router.post(
    "/patients/{patient_id}/appointments/{appointment_id}/cancel",
    response_model=AdminAppointmentResponse,
)
def cancel_patient_appointment(
    patient_id: UUID,
    appointment_id: UUID,
    data: AppointmentCancelRequest,
    current_patient: CurrentPatient,
    appointments: Appointments,
    users: Users,
):
    try:
        return AppointmentService(appointments, users).cancel_appointment(
            patient_id,
            appointment_id,
            current_patient,
            data,
            enforce_patient_notice=True,
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error