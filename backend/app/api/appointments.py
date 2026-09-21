from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_appointment_repository,
    get_current_admin,
    get_user_repository,
)
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointments import (
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


router = APIRouter(prefix="/admin", tags=["admin-appointments"])
AdminUser = Annotated[User, Depends(get_current_admin)]
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