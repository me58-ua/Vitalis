from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_appointment_repository, get_video_session_repository
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.video_session_repository import VideoSessionRepository
from app.schemas.video import VideoJoinResponse
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
