# Dispatcher de notificaciones: crea recordatorios de citas y procesa el envío de correos pendientes.
from datetime import datetime, timedelta, timezone
from smtplib import SMTPException

from app.models import AppointmentStatus, EmailStatus
from app.config import settings
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import send_product_notification_email
from app.services.notification_service import NotificationService


class NotificationDispatcher:
    def __init__(
        self,
        notifications: NotificationRepository,
        users: UserRepository,
        appointments: AppointmentRepository | None = None,
        max_attempts: int = 3,
    ):
        self.notifications = notifications
        self.users = users
        self.appointments = appointments
        self.service = NotificationService(notifications, max_attempts)
        self.max_attempts = max_attempts

    def run_once(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        self._create_reminders(now)
        processed = 0
        for notification in self.notifications.due_for_email(now, self.max_attempts):
            user = self.users.get_by_id(notification.recipient_id)
            attempts = notification.email_attempts + 1
            if user is None:
                self.notifications.update_email_result(
                    notification, EmailStatus.FAILED, attempts, None
                )
                processed += 1
                continue
            profile = getattr(user, "professional_profile", None)
            if profile is not None and getattr(profile, "email_notifications_enabled", True) is False:
                notification.email_required = False
                self.notifications.update_email_result(notification, EmailStatus.NOT_APPLICABLE, notification.email_attempts, None)
                processed += 1
                continue
            try:
                sent = send_product_notification_email(
                    user.email,
                    notification.title,
                    notification.message,
                    f"{settings.FRONTEND_URL.rstrip('/')}/notifications/{notification.id}",
                )
            except (OSError, SMTPException):
                sent = False
            status = EmailStatus.SENT if sent else EmailStatus.FAILED
            self.notifications.update_email_result(
                notification,
                status,
                attempts,
                now if sent else None,
            )
            processed += 1
        return processed

    def _create_reminders(self, now: datetime) -> None:
        if self.appointments is None:
            return
        for appointment in self.appointments.list_upcoming(now, now + timedelta(hours=24, minutes=1)):
            if appointment.status != AppointmentStatus.CONFIRMED:
                continue
            for hours, notification_type in (
                (24, "appointment_reminder_24h"),
                (1, "appointment_reminder_1h"),
            ):
                reminder_time = appointment.start_time - timedelta(hours=hours)
                if reminder_time <= now:
                    for recipient_id in (appointment.patient_id, appointment.professional_id):
                        self.service.notify(
                            recipient_id,
                            notification_type,
                            entity="appointment",
                            entity_id=appointment.id,
                            scheduled_for=reminder_time,
                            email_required=True,
                        )
