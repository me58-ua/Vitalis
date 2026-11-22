from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import get_current_user, get_current_patient, get_appointment_repository, get_video_session_repository, get_audit_repository
from app.repositories.audit_repository import AuditRepository
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.video_session_repository import VideoSessionRepository
from app.schemas.video import VideoJoinResponse, VideoAttendanceRequest, VideoAttendanceResponse, PatientAppointmentPage
from app.services.video_service import (
    VideoConfigurationError,
    VideoForbiddenError,
    VideoNotFoundError,
    VideoService,
)

router = APIRouter(tags=["video"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Events = Annotated[VideoSessionRepository, Depends(get_video_session_repository)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]


@router.get("/patients/me/appointments", response_model=PatientAppointmentPage)
def patient_appointments(user: Annotated[User, Depends(get_current_patient)], appointments: Appointments,
                         response: Response, page: Annotated[int, Query(ge=1)] = 1,
                         page_size: Annotated[int, Query(ge=1, le=100)] = 20,
                         confirmed_only: bool = False):
    response.headers["Cache-Control"] = "no-store"
    rows, total = appointments.list_patient_appointments(user.id, (page - 1) * page_size, page_size, confirmed_only)
    return {"appointments": rows, "total": total, "page": page, "page_size": page_size}


@router.post("/appointments/{appointment_id}/video/attendance", response_model=VideoAttendanceResponse)
def video_attendance(appointment_id: UUID, data: VideoAttendanceRequest, user: CurrentUser,
                     appointments: Appointments, events: Events, audits: Audits):
    try:
        return VideoService(appointments, events, audits).record_attendance(appointment_id, user, data.event)
    except VideoNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except VideoForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.post("/appointments/{appointment_id}/video/join", response_model=VideoJoinResponse)
def join_video(
    appointment_id: UUID,
    user: CurrentUser,
    appointments: Appointments,
    events: Events,
):
    try:
        return VideoService(appointments, events).create_join_session(appointment_id, user)
    except VideoNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except VideoForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except VideoConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
