import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.models import EmailStatus
from app.services.notification_dispatcher import NotificationDispatcher
from app.services.notification_service import NotificationService


class FakeNotificationRepository:
    def __init__(self):
        self.items = []

    def find_duplicate(self, recipient_id, notification_type, entity_id, scheduled_for):
        return next(
            (
                item for item in self.items
                if (item.recipient_id, item.type, item.entity_id, item.scheduled_for)
                == (recipient_id, notification_type, entity_id, scheduled_for)
            ),
            None,
        )

    def create(self, notification):
        notification.id = uuid.uuid4()
        notification.created_at = notification.scheduled_for or datetime.now(timezone.utc)
        self.items.append(notification)
        return notification

    def find_recent(self, recipient_id, notification_type, entity_id, since):
        return next(
            (
                item for item in self.items
                if item.recipient_id == recipient_id
                and item.type == notification_type
                and item.entity_id == entity_id
                and item.created_at > since
            ),
            None,
        )

    def due_for_email(self, now, max_attempts=3):
        return [
            item for item in self.items
            if item.email_required
            and item.email_status in (EmailStatus.PENDING, EmailStatus.FAILED)
            and item.scheduled_for <= now
            and item.email_attempts < max_attempts
        ]

    def update_email_result(self, notification, status, attempts, sent_at):
        notification.email_status = status
        notification.email_attempts = attempts
        notification.sent_at = sent_at
        return notification


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.recipient_id = uuid.uuid4()
        self.appointment_id = uuid.uuid4()
        self.repository = FakeNotificationRepository()
        self.service = NotificationService(self.repository, max_email_attempts=2)

    def test_deduplicates_same_event(self):
        first = self.service.notify(
            self.recipient_id,
            "appointment_reminder_24h",
            entity="appointment",
            entity_id=self.appointment_id,
            scheduled_for=datetime(2026, 10, 6, tzinfo=timezone.utc),
        )
        second = self.service.notify(
            self.recipient_id,
            "appointment_reminder_24h",
            entity="appointment",
            entity_id=self.appointment_id,
            scheduled_for=first.scheduled_for,
        )
        self.assertIs(first, second)
        self.assertEqual(len(self.repository.items), 1)

    def test_chat_notifications_are_throttled_for_ten_minutes(self):
        first = self.service.notify_chat_throttled(
            self.recipient_id, self.appointment_id, datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
        )
        second = self.service.notify_chat_throttled(
            self.recipient_id, self.appointment_id, datetime(2026, 10, 5, 10, 9, tzinfo=timezone.utc)
        )
        third = self.service.notify_chat_throttled(
            self.recipient_id, self.appointment_id, datetime(2026, 10, 5, 10, 10, tzinfo=timezone.utc)
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertIsNotNone(third)

    def test_dispatcher_retries_until_limit(self):
        notification = self.service.notify(
            self.recipient_id,
            "new_message",
            entity="appointment",
            entity_id=self.appointment_id,
            scheduled_for=datetime(2026, 10, 5, tzinfo=timezone.utc),
            email_required=True,
        )
        users = SimpleNamespace(get_by_id=lambda _: SimpleNamespace(email="person@example.com"))
        dispatcher = NotificationDispatcher(self.repository, users, max_attempts=2)
        with patch("app.services.notification_dispatcher.send_product_notification_email", return_value=False):
            dispatcher.run_once(datetime(2026, 10, 5, 1, tzinfo=timezone.utc))
            dispatcher.run_once(datetime(2026, 10, 5, 2, tzinfo=timezone.utc))
            dispatcher.run_once(datetime(2026, 10, 5, 3, tzinfo=timezone.utc))
        self.assertEqual(notification.email_attempts, 2)
        self.assertEqual(notification.email_status, EmailStatus.FAILED)

    def test_dispatcher_creates_only_reminders_inside_window(self):
        appointment = SimpleNamespace(
            id=self.appointment_id,
            patient_id=self.recipient_id,
            professional_id=uuid.uuid4(),
            status="confirmed",
            start_time=datetime(2026, 10, 6, 12, tzinfo=timezone.utc),
        )
        appointments = SimpleNamespace(list_upcoming=lambda start, end: [appointment])
        users = SimpleNamespace(get_by_id=lambda _: SimpleNamespace(email="person@example.com"))
        dispatcher = NotificationDispatcher(self.repository, users, appointments)
        dispatcher.run_once(datetime(2026, 10, 5, 12, tzinfo=timezone.utc))
        self.assertEqual(len(self.repository.items), 2)


if __name__ == "__main__":
    unittest.main()
