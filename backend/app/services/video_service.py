# Servicio de videollamadas: crea, valida y finaliza sesiones de video para las citas.
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import Appointment, AppointmentStatus, AppointmentStatusHistory, AppointmentType, AuditAction, User, VideoSessionEvent
from app.services.audit_service import AuditService
from app.services.daily_client import DailyClient
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.video_session_repository import VideoSessionRepository


PROFESSIONAL_JOIN_GRACE = timedelta(hours=1)


class VideoNotFoundError(Exception):
    pass


class VideoForbiddenError(Exception):
    pass


class VideoConfigurationError(Exception):
    pass


class VideoService:
    def __init__(self, appointments: AppointmentRepository, events: VideoSessionRepository, audits=None):
        self.appointments = appointments
        self.events = events
        self.audit = AuditService(audits)

    def expire_professional_no_shows(self, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - PROFESSIONAL_JOIN_GRACE
        expired = 0
        for appointment in self.appointments.lock_overdue_unattended_video(cutoff):
            # Recheck after taking the same row lock used to record attendance.
            if self._professional_joined(appointment):
                continue
            appointment.status = AppointmentStatus.NO_SHOW_PROFESSIONAL
            self.appointments.save(appointment)
            self.appointments.create_status_history(AppointmentStatusHistory(
                appointment_id=appointment.id, old_status=AppointmentStatus.CONFIRMED,
                new_status=appointment.status, changed_by=None,
                reason="El profesional no se conectó durante la primera hora desde el inicio previsto.",
            ))
            self.audit.record(None, None, AuditAction.UPDATE, "appointment_professional_no_show",
                              appointment.id, appointment.patient_id)
            expired += 1
        return expired

    def _professional_joined(self, appointment: Appointment) -> bool:
        return self.events.has_event(appointment.id, appointment.professional_id, "joined")

    @staticmethod
    def _join_deadline_passed(appointment: Appointment, now: datetime) -> bool:
        start = appointment.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return now >= start + PROFESSIONAL_JOIN_GRACE

    def record_attendance(self, appointment_id: UUID, user: User, event: str):
        # Serialize concurrent departures so completion/history are written once.
        appointment = self.appointments.lock_appointment(appointment_id)
        if appointment is None:
            raise VideoNotFoundError("Appointment not found")
        if not user.is_active or user.id not in (appointment.patient_id, appointment.professional_id):
            raise VideoForbiddenError("User cannot join this appointment")
        if appointment.type != AppointmentType.VIDEO or appointment.status not in (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED):
            raise VideoForbiddenError("Video is unavailable for this appointment")
        if (appointment.status == AppointmentStatus.CONFIRMED
                and self._join_deadline_passed(appointment, datetime.now(timezone.utc))
                and not self._professional_joined(appointment)):
            raise VideoForbiddenError("Video join window is closed")
        # The browser reports the SDK's local joined event; token issuance alone
        # must never mark an unattended appointment completed.
        if not self.events.has_event(appointment_id, user.id, "token_issued"):
            raise VideoForbiddenError("No video access was issued for this participant")
        if event == "left" and not self.events.has_event(appointment_id, user.id, "joined"):
            raise VideoForbiddenError("Participant has not joined this video appointment")
        if not self.events.has_event(appointment_id, user.id, event):
            self.events.create(VideoSessionEvent(appointment_id=appointment_id, user_id=user.id, event=event))
        if event == "left" and appointment.status == AppointmentStatus.CONFIRMED and self._professional_joined(appointment):
            appointment.status = AppointmentStatus.COMPLETED
            self.appointments.save(appointment)
            self.appointments.create_status_history(AppointmentStatusHistory(
                appointment_id=appointment_id, old_status=AppointmentStatus.CONFIRMED,
                new_status=AppointmentStatus.COMPLETED, changed_by=user.id,
                reason="Participant ended the attended video consultation",
            ))
            self.audit.record(user.id, user.role, AuditAction.UPDATE, "appointment", appointment_id, appointment.patient_id)
        # No command is sent to Daily: the other participant keeps their session.
        return {"status": appointment.status}

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
        now = datetime.now(timezone.utc)
        if self._join_deadline_passed(appointment, now) and not self._professional_joined(appointment):
            raise VideoForbiddenError("Video join window is closed")
        start = appointment.start_time.astimezone(ZoneInfo("Europe/Madrid"))
        local_now = now.astimezone(ZoneInfo("Europe/Madrid"))
        window_start = start - timedelta(minutes=settings.VIDEO_JOIN_EARLY_MINUTES)
        if local_now < window_start:
            raise VideoForbiddenError("Video join window is closed")

        if not settings.DAILY_API_KEY.strip():
            raise VideoConfigurationError("Daily is not configured")

        daily = DailyClient(settings.DAILY_API_KEY)
        room_name = f"vitalis-{appointment.id.hex}"
        room_url = daily.get_or_create_room(room_name)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.DAILY_TOKEN_TTL_SECONDS)
        token = daily.create_token(room_name, user.id, expires_at)
        self.events.create(
            VideoSessionEvent(
                appointment_id=appointment.id,
                user_id=user.id,
                event="token_issued",
            )
        )
        return {
            "room_url": room_url,
            "token": token,
            "expires_at": expires_at,
        }
