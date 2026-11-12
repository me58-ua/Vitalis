import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import AppointmentStatus, AppointmentType, UserRole
from app.services.chat_service import (
    ChatForbiddenError,
    ChatNotFoundError,
    ChatService,
    ChatValidationError,
)


class FakeAppointmentRepository:
    def __init__(self, appointment=None):
        self.appointment = appointment

    def get_appointment(self, appointment_id):
        return self.appointment if self.appointment and self.appointment.id == appointment_id else None


class FakeMessageRepository:
    def __init__(self):
        self.messages = []

    def create(self, message):
        message.id = uuid.uuid4()
        message.sent_at = datetime.now(timezone.utc)
        self.messages.append(message)
        return message

    def list_by_appointment(self, appointment_id, limit, before_id=None):
        messages = [message for message in self.messages if message.appointment_id == appointment_id]
        if before_id:
            index = next(index for index, message in enumerate(messages) if message.id == before_id)
            messages = messages[:index]
        return list(reversed(messages[-limit:]))

    def get_after(self, appointment_id, after_id):
        messages = [message for message in self.messages if message.appointment_id == appointment_id]
        index = next(index for index, message in enumerate(messages) if message.id == after_id)
        return messages[index + 1 :]


class ChatServiceTests(unittest.TestCase):
    def setUp(self):
        self.patient = SimpleNamespace(id=uuid.uuid4(), role=UserRole.PATIENT, is_active=True, name="Patient")
        self.professional = SimpleNamespace(
            id=uuid.uuid4(), role=UserRole.PROFESSIONAL, is_active=True, name="Professional"
        )
        self.third_party = SimpleNamespace(id=uuid.uuid4(), role=UserRole.PATIENT, is_active=True)
        self.appointment = SimpleNamespace(
            type=AppointmentType.VIDEO,
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            professional_id=self.professional.id,
            status=AppointmentStatus.CONFIRMED,
            start_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=55),
        )
        self.appointments = FakeAppointmentRepository(self.appointment)
        self.messages = FakeMessageRepository()
        self.service = ChatService(self.appointments, self.messages, timedelta(hours=1), 10)

    def test_patient_and_professional_can_access_room(self):
        self.assertIs(self.service.get_room_access(self.appointment.id, self.patient), self.appointment)
        self.assertIs(self.service.get_room_access(self.appointment.id, self.professional), self.appointment)

    def test_third_party_and_inactive_user_are_rejected(self):
        with self.assertRaises(ChatForbiddenError):
            self.service.get_room_access(self.appointment.id, self.third_party)
        self.patient.is_active = False
        with self.assertRaises(ChatForbiddenError):
            self.service.get_room_access(self.appointment.id, self.patient)

    def test_matching_id_with_wrong_role_is_rejected(self):
        self.patient.role = UserRole.ADMIN
        with self.assertRaises(ChatForbiddenError):
            self.service.get_room_access(self.appointment.id, self.patient)

    def test_in_person_appointments_have_no_chat(self):
        self.appointment.type = AppointmentType.IN_PERSON
        with self.assertRaises(ChatForbiddenError):
            self.service.get_room_access(self.appointment.id, self.patient)

    def test_writing_is_only_allowed_during_the_appointment(self):
        start, end = self.appointment.start_time, self.appointment.end_time
        self.assertFalse(self.service.can_write(self.appointment, start - timedelta(seconds=1)))
        self.assertTrue(self.service.can_write(self.appointment, start))
        self.assertTrue(self.service.can_write(self.appointment, end))
        self.assertFalse(self.service.can_write(self.appointment, end + timedelta(seconds=1)))

    def test_missing_and_cancelled_appointments_are_rejected(self):
        with self.assertRaises(ChatNotFoundError):
            self.service.get_room_access(uuid.uuid4(), self.patient)
        self.appointment.status = AppointmentStatus.CANCELLED
        with self.assertRaises(ChatForbiddenError):
            self.service.get_room_access(self.appointment.id, self.patient)

    def test_completed_is_readable_but_not_writable(self):
        self.appointment.status = AppointmentStatus.COMPLETED
        self.assertIsNotNone(self.service.get_room_access(self.appointment.id, self.patient))
        with self.assertRaises(ChatForbiddenError):
            self.service.save_message(self.appointment.id, self.patient, "hello")

    def test_save_normalizes_and_rejects_invalid_content(self):
        message = self.service.save_message(self.appointment.id, self.patient, "  hello  ")
        self.assertEqual(message.content, "hello")
        for content in ("   ", "12345678901"):
            with self.subTest(content=content):
                with self.assertRaises(ChatValidationError):
                    self.service.save_message(self.appointment.id, self.patient, content)

    def test_list_is_chronological_and_supports_cursor(self):
        first = self.service.save_message(self.appointment.id, self.patient, "first")
        second = self.service.save_message(self.appointment.id, self.professional, "second")
        third = self.service.save_message(self.appointment.id, self.patient, "third")
        self.assertEqual([message.content for message in self.service.list_messages(self.appointment.id, self.patient, 50)], ["first", "second", "third"])
        self.assertEqual([message.content for message in self.service.list_messages(self.appointment.id, self.patient, 50, after_id=first.id)], ["second", "third"])
        self.assertEqual([message.content for message in self.service.list_messages(self.appointment.id, self.patient, 1)], ["third"])
        self.assertEqual(third.content, "third")


if __name__ == "__main__":
    unittest.main()
