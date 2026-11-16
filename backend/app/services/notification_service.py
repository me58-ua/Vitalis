# Servicio de notificaciones: crea notificaciones y limita mensajes repetidos del chat.
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models import EmailStatus, Notification
from app.repositories.notification_repository import NotificationRepository


GENERIC_MESSAGES = {
    "new_message": ("Nuevo mensaje", "Tienes un nuevo mensaje sobre tu cita"),
    "appointment_confirmed": ("Cita confirmada", "Tu cita ha sido confirmada"),
    "appointment_cancelled": ("Cita cancelada", "Tu cita ha sido cancelada"),
    "appointment_rescheduled": ("Cita actualizada", "La hora de tu cita ha sido actualizada"),
    "appointment_reminder_24h": ("Recordatorio de cita", "Tienes una cita mañana"),
    "appointment_reminder_1h": ("Recordatorio de cita", "Tienes una cita dentro de una hora"),
}

RISK_MESSAGE = (
    "Según tu perfil te recomendamos reservar una revisión. "
    "Este resultado podría beneficiarte de una consulta. "
    "Entra en Vitalis para ver el detalle. Esto no es un diagnóstico."
)


class NotificationService:
    def __init__(self, repository: NotificationRepository, max_email_attempts: int = 3):
        self.repository = repository
        self.max_email_attempts = max_email_attempts

    def notify_professional_review(self, user, *, profile_change: bool = False) -> None:
        now = datetime.now(timezone.utc)
        notification_type = "professional_profile_change_pending" if profile_change else "professional_registration_pending"
        title = "Cambio de perfil pendiente" if profile_change else "Nuevo profesional pendiente de aprobación"
        message = (
            f"{user.name} ha solicitado cambios en su perfil profesional. Revisa la solicitud en Gestión de usuarios."
            if profile_change else
            f"{user.name} se ha registrado como profesional y necesita tu aprobación. Revisa la solicitud en Gestión de usuarios."
        )
        for admin_id in self.repository.active_admin_ids():
            self.notify(admin_id, notification_type, entity="professional", entity_id=user.id,
                        scheduled_for=now, title=title, message=message)

    def notify(
        self,
        recipient_id: UUID,
        notification_type: str,
        *,
        entity: str | None = None,
        entity_id: UUID | None = None,
        scheduled_for: datetime | None = None,
        email_required: bool = False,
        title: str | None = None,
        message: str | None = None,
    ) -> Notification:
        scheduled_for = scheduled_for or datetime.now(timezone.utc)
        existing = self.repository.find_duplicate(
            recipient_id, notification_type, entity_id, scheduled_for
        )
        if existing is not None:
            return existing
        default_title, default_message = GENERIC_MESSAGES.get(
            notification_type, ("Notification", "You have a new notification")
        )
        notification = Notification(
            recipient_id=recipient_id,
            type=notification_type,
            title=title or default_title,
            message=message or default_message,
            entity=entity,
            entity_id=entity_id,
            scheduled_for=scheduled_for,
            email_required=email_required,
            email_status=EmailStatus.PENDING if email_required else EmailStatus.NOT_APPLICABLE,
            email_attempts=0,
        )
        try:
            return self.repository.create(notification)
        except IntegrityError:
            rollback = getattr(self.repository, "rollback", None)
            if rollback is not None:
                rollback()
            duplicate = self.repository.find_duplicate(recipient_id, notification_type, entity_id, scheduled_for)
            if duplicate is not None:
                return duplicate
            raise

    def notify_chat_throttled(
        self, recipient_id: UUID, appointment_id: UUID, now: datetime | None = None
    ) -> Notification | None:
        now = now or datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=10)
        existing = self.repository.find_recent(
            recipient_id, "new_message", appointment_id, window_start
        )
        if existing is not None:
            return None
        return self.notify(
            recipient_id,
            "new_message",
            entity="appointment",
            entity_id=appointment_id,
            email_required=True,
            scheduled_for=now,
        )

    def notify_risks_calculated(self, recipient_id: UUID, patient_id: UUID):
        return self.notify(
            recipient_id,
            "risks_calculated",
            entity="risk_assessment",
            entity_id=patient_id,
            email_required=True,
            title="Cálculo de riesgos completado",
            message="Hemos calculado tus riesgos con los datos guardados al finalizar la conversación. Entra en Vitalis para consultar los resultados.",
        )

    def notify_risk(self, recipient_id: UUID, model: str, alert_level: str, now: datetime | None = None):
        if alert_level == "none":
            return None
        now = now or datetime.now(timezone.utc)
        notification_type = f"risk_{model}"
        find_recent = getattr(self.repository, "find_recent_by_type", None)
        if find_recent is not None and find_recent(
            recipient_id, notification_type, now - timedelta(days=30)
        ) is not None:
            return None
        if model == "family_huntington":
            message = (
                "Según tu perfil te recomendamos reservar una revisión. "
                "Podría beneficiarte de una consulta. "
                "Entra en Vitalis para ver el detalle. Esto no es un diagnóstico."
            )
        else:
            message = RISK_MESSAGE
        return self.notify(
            recipient_id,
            notification_type,
            entity="risk_assessment",
            entity_id=recipient_id,
            scheduled_for=now,
            email_required=alert_level == "recommend_appointment",
            title="Revisión recomendada",
            message=message,
        )
