from datetime import timedelta
from uuid import UUID

from app.models import Appointment, AppointmentStatus, ChatMessage, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.chat_message_repository import ChatMessageRepository


DEFAULT_CHAT_WRITE_WINDOW = timedelta(hours=24)
MAX_CHAT_MESSAGE_LENGTH = 2000


class ChatNotFoundError(Exception):
    pass


class ChatForbiddenError(Exception):
    pass


class ChatValidationError(Exception):
    pass


class ChatService:
    def __init__(
        self,
        appointments: AppointmentRepository,
        messages: ChatMessageRepository | None = None,
        write_window: timedelta = DEFAULT_CHAT_WRITE_WINDOW,
        max_message_length: int = MAX_CHAT_MESSAGE_LENGTH,
    ):
        self.appointments = appointments
        self.messages = messages
        self.write_window = write_window
        self.max_message_length = max_message_length

    def get_room_access(self, appointment_id: UUID, user: User) -> Appointment:
        appointment = self.appointments.get_appointment(appointment_id)
        if appointment is None:
            raise ChatNotFoundError("Appointment not found")
        if not getattr(user, "is_active", True):
            raise ChatForbiddenError("User is inactive")
        if user.id not in (appointment.patient_id, appointment.professional_id):
            raise ChatForbiddenError("User does not participate in this appointment")
        if appointment.status not in (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED):
            raise ChatForbiddenError("Chat is unavailable for this appointment status")
        return appointment

    def can_write(self, appointment: Appointment, now=None) -> bool:
        if appointment.status != AppointmentStatus.CONFIRMED:
            return False
        if now is None:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
        start = appointment.start_time
        end = appointment.end_time + self.write_window
        return start - self.write_window <= now <= end

    def save_message(self, appointment_id: UUID, sender: User, content: str) -> ChatMessage:
        appointment = self.get_room_access(appointment_id, sender)
        if not self.can_write(appointment):
            raise ChatForbiddenError("Chat is not writable")
        normalized = content.strip()
        if not normalized:
            raise ChatValidationError("Message content cannot be empty")
        if len(normalized) > self.max_message_length:
            raise ChatValidationError("Message content is too long")
        if self.messages is None:
            raise RuntimeError("Chat message repository is required")
        # Extension point for Issue 25: enqueue a product email after persistence.
        return self.messages.create(
            ChatMessage(appointment_id=appointment.id, sender_id=sender.id, content=normalized)
        )

    def list_messages(
        self,
        appointment_id: UUID,
        user: User,
        limit: int,
        before_id: UUID | None = None,
        after_id: UUID | None = None,
    ) -> list[ChatMessage]:
        self.get_room_access(appointment_id, user)
        if self.messages is None:
            raise RuntimeError("Chat message repository is required")
        limit = min(max(limit, 1), 100)
        if after_id is not None:
            return self.messages.get_after(appointment_id, after_id)[:limit]
        return list(reversed(self.messages.list_by_appointment(appointment_id, limit, before_id)))
