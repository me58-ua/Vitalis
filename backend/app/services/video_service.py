# Servicio de videollamadas: crea, valida y finaliza sesiones de video para las citas.
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
import secrets

from jose import jwt

from app.config import settings
from app.models import Appointment, AppointmentStatus, AppointmentType, User, UserRole, VideoSessionEvent
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.video_session_repository import VideoSessionRepository


class VideoNotFoundError(Exception):
    pass


class VideoForbiddenError(Exception):
    pass


class VideoConfigurationError(Exception):
    pass


class VideoService:
    def __init__(self, appointments: AppointmentRepository, events: VideoSessionRepository):
        self.appointments = appointments
        self.events = events

    def create_join_session(self, appointment_id: UUID, user: User) -> dict:
        appointment = self.appointments.get_appointment(appointment_id)
        if appointment is None:
            raise VideoNotFoundError("Appointment not found")
        if not getattr(user, "is_active", True) or user.id not in (
            appointment.patient_id,
            appointment.professional_id,
        ):
            raise VideoForbiddenError("User cannot join this appointment")
        if appointment.type != AppointmentType.VIDEO or appointment.status != AppointmentStatus.CONFIRMED:
            raise VideoForbiddenError("Video is unavailable for this appointment")
        if (
            not settings.JITSI_DOMAIN
            or not settings.JITSI_XMPP_DOMAIN
            or not settings.JITSI_APP_ID
            or not settings.JITSI_APP_SECRET
        ):
            raise VideoConfigurationError("Jitsi is not configured")

        now = datetime.now(timezone.utc)
        start = appointment.start_time.astimezone(ZoneInfo("Europe/Madrid"))
        local_now = now.astimezone(ZoneInfo("Europe/Madrid"))
        window_start = start - timedelta(minutes=settings.VIDEO_JOIN_EARLY_MINUTES)
        if local_now < window_start:
            raise VideoForbiddenError("Video join window is closed")

        if not isinstance(appointment.room_id, str) or len(appointment.room_id) < 32:
            appointment.room_id = secrets.token_urlsafe(24)
            self.appointments.save(appointment)

        expires_at = now + timedelta(seconds=settings.JITSI_TOKEN_TTL_SECONDS)
        payload = {
            "aud": "jitsi",
            "iss": settings.JITSI_APP_ID,
            "sub": settings.JITSI_XMPP_DOMAIN,
            "room": appointment.room_id,
            "exp": int(expires_at.timestamp()),
            "nbf": int(now.timestamp()),
            "context": {
                "user": {
                    "id": str(user.id),
                    "name": user.name,
                }
            },
        }
        if user.role == UserRole.PROFESSIONAL:
            payload["moderator"] = True
        token = jwt.encode(payload, settings.JITSI_APP_SECRET, algorithm="HS256")
        self.events.create(
            VideoSessionEvent(
                appointment_id=appointment.id,
                user_id=user.id,
                event="token_issued",
            )
        )
        return {
            "domain": settings.JITSI_DOMAIN,
            "room_name": appointment.room_id,
            "jwt": token,
            "expires_at": expires_at,
        }
