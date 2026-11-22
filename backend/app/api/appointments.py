from typing import Annotated
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.schemas.admin_appointments import AdminAppointmentsQuery, AdminAppointmentListResponse, AdminUpcomingAppointmentsResponse
from app.services.admin_appointment_service import AdminAppointmentQueryService

from app.api.deps import (
    get_appointment_repository,
    get_current_admin,
    get_current_patient,
    get_audit_repository,
    get_professional_repository,
    get_user_repository,
    get_notification_service,
)
from app.models import AppointmentType, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.appointments import (
    AdminAppointmentUpdate,
    AppointmentCancelRequest,
    AdminAppointmentCreate,
    AdminAppointmentResponse,
    AdminScheduleCreate,
    AdminScheduleResponse,
    AvailabilityResponse,
    AvailabilitySlot,
    PatientAppointmentCreate,
    PatientAppointmentFollowUp,
    PatientAppointmentHistory,
    PatientAppointmentHistoryQuery,
)
from app.services.appointment_service import (
    AppointmentAccessError,
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentService,
    AppointmentValidationError,
)
from app.services.schedule_service import ScheduleService
from app.services.notification_service import NotificationService


router = APIRouter(prefix="/admin", tags=["admin-appointments"])
patient_router = APIRouter(tags=["patient-appointments"])
AdminUser = Annotated[User, Depends(get_current_admin)]
CurrentPatient = Annotated[User, Depends(get_current_patient)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Users = Annotated[UserRepository, Depends(get_user_repository)]
Professionals = Annotated[ProfessionalRepository, Depends(get_professional_repository)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]
Notifications = Annotated[NotificationService, Depends(get_notification_service)]


@patient_router.get("/patients/me/appointments/history", response_model=PatientAppointmentHistory)
def patient_appointment_history(
    current_patient: CurrentPatient, appointments: Appointments, response: Response,
    query: Annotated[PatientAppointmentHistoryQuery, Query()],
):
    zone = ZoneInfo("Europe/Madrid")
    first = query.from_date or query.to_date
    last = query.to_date or query.from_date
    start = datetime.combine(first, time.min, tzinfo=zone).astimezone(timezone.utc) if first else None
    end = (datetime.combine(last + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
           if last and last < date.max else None)
    rows, total = appointments.list_patient_appointment_history(
        current_patient.id, start, end, query.doctor.strip(),
        (query.page - 1) * query.page_size, query.page_size,
    )
    response.headers["Cache-Control"] = "no-store"
    return PatientAppointmentHistory(appointments=rows, total=total, page=query.page, page_size=query.page_size)


@patient_router.get("/patients/me/appointments/{appointment_id}/follow-up", response_model=PatientAppointmentFollowUp)
def patient_appointment_follow_up(
    appointment_id: UUID, current_patient: CurrentPatient, appointments: Appointments, response: Response,
):
    appointment = appointments.get_patient_appointment_history_detail(current_patient.id, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    response.headers["Cache-Control"] = "no-store"
    return appointment


@router.get("/appointments", response_model=AdminAppointmentListResponse)
def list_admin_appointments(_: AdminUser, appointments: Appointments, query: Annotated[AdminAppointmentsQuery, Query()]):
    return AdminAppointmentQueryService(appointments).list(query)


@router.get("/appointments/upcoming-month", response_model=AdminUpcomingAppointmentsResponse)
def upcoming_admin_appointments(_: AdminUser, appointments: Appointments, limit: int = Query(default=3, ge=1, le=10)):
    return AdminAppointmentQueryService(appointments).upcoming_month(limit)


@router.post("/schedules", response_model=AdminScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: AdminScheduleCreate,
    _: AdminUser,
    appointments: Appointments,
    users: Users,
):
    try:
        return ScheduleService(appointments, users).create_schedule(data)
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/appointments", response_model=AdminAppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    data: AdminAppointmentCreate,
    _: AdminUser,
    appointments: Appointments,
    users: Users,
    professionals: Professionals,
):
    try:
        return AppointmentService(appointments, users, professionals).create_appointment(data)
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except AppointmentConflictError as error:
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
    professionals: Professionals,
    audits: Audits,
    notifications: Notifications,
):
    try:
        return AppointmentService(appointments, users, professionals, audits=audits, notifications=notifications).update_as_admin(
            appointment_id, data, current_admin
        )
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except AppointmentConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@patient_router.get(
    "/professionals/{professional_id}/availability",
    response_model=AvailabilityResponse,
)
def professional_availability(
    professional_id: UUID,
    requested_date: date,
    appointment_type: AppointmentType,
    current_patient: CurrentPatient,
    appointments: Appointments,
    users: Users,
    professionals: Professionals,
    response: Response,
):
    try:
        slots = AppointmentService(appointments, users, professionals).list_available_slots(
            professional_id, requested_date, appointment_type, current_patient.id
        )
        response.headers["Cache-Control"] = "no-store"
        return AvailabilityResponse(
            professional_id=professional_id,
            date=requested_date,
            slots=[
                AvailabilitySlot(start_time=start, end_time=end, type=appointment_type)
                for start, end in slots
            ],
        )
    except AppointmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AppointmentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@patient_router.post(
    "/patients/me/appointments",
    response_model=AdminAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient_appointment(
    data: PatientAppointmentCreate,
    current_patient: CurrentPatient,
    appointments: Appointments,
    users: Users,
    professionals: Professionals,
):
    try:
        return AppointmentService(appointments, users, professionals).create_for_patient(
            current_patient, data
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
    professionals: Professionals,
    audits: Audits,
    notifications: Notifications,
):
    try:
        return AppointmentService(appointments, users, professionals, audits=audits, notifications=notifications).cancel_appointment(
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
