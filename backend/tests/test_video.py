import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from jose import jwt

from app.config import settings
from app.models import AppointmentStatus, AppointmentType, UserRole
from app.services.video_service import VideoForbiddenError, VideoService


class FakeAppointmentRepository:
    def __init__(self, appointment):
        self.appointment = appointment

    def get_appointment(self, appointment_id):
        return self.appointment if self.appointment.id == appointment_id else None

    def save(self, appointment):
        return appointment


class FakeEventRepository:
    def __init__(self):
        self.events = []

    def create(self, event):
        self.events.append(event)
        return event


class VideoServiceTests(unittest.TestCase):
    def setUp(self):
        self.patient = SimpleNamespace(id=uuid.uuid4(), name="Patient", role=UserRole.PATIENT, is_active=True)
        self.professional = SimpleNamespace(id=uuid.uuid4(), name="Doctor", role=UserRole.PROFESSIONAL, is_active=True)
        now = datetime.now(timezone.utc)
        self.appointment = SimpleNamespace(
            id=uuid.uuid4(), patient_id=self.patient.id, professional_id=self.professional.id,
            type=AppointmentType.VIDEO, status=AppointmentStatus.CONFIRMED,
            start_time=now - timedelta(minutes=2), end_time=now + timedelta(minutes=30), room_id=None,
        )
        self.events = FakeEventRepository()
        self.service = VideoService(FakeAppointmentRepository(self.appointment), self.events)
        self.config = patch.multiple(
            settings,
            JITSI_DOMAIN="video.example.com",
            JITSI_APP_ID="vitalis",
            JITSI_APP_SECRET="test-secret",
            JITSI_TOKEN_TTL_SECONDS=3600,
            VIDEO_JOIN_EARLY_MINUTES=10,
            VIDEO_JOIN_LATE_MINUTES=30,
        )
        self.config.start()

    def tearDown(self):
        self.config.stop()

    def test_participant_gets_valid_token_and_room_is_stable(self):
        first = self.service.create_join_session(self.appointment.id, self.patient)
        second = self.service.create_join_session(self.appointment.id, self.patient)
        claims = jwt.decode(first["jwt"], "test-secret", algorithms=["HS256"], audience="jitsi")
        self.assertEqual(first["room_name"], second["room_name"])
        self.assertEqual(claims["room"], first["room_name"])
        self.assertEqual(claims["context"]["user"]["id"], str(self.patient.id))
        self.assertNotIn("moderator", claims)
        self.assertEqual(len(self.events.events), 2)

    def test_only_professional_gets_moderator_claim(self):
        result = self.service.create_join_session(self.appointment.id, self.professional)
        claims = jwt.decode(result["jwt"], "test-secret", algorithms=["HS256"], audience="jitsi")
        self.assertTrue(claims["moderator"])

    def test_third_party_and_non_video_are_rejected(self):
        third_party = SimpleNamespace(id=uuid.uuid4(), role=UserRole.PATIENT, is_active=True)
        with self.assertRaises(VideoForbiddenError):
            self.service.create_join_session(self.appointment.id, third_party)
        self.appointment.type = AppointmentType.IN_PERSON
        with self.assertRaises(VideoForbiddenError):
            self.service.create_join_session(self.appointment.id, self.patient)

    def test_join_outside_time_window_is_rejected(self):
        self.appointment.start_time = datetime.now(timezone.utc) - timedelta(hours=2)
        self.appointment.end_time = datetime.now(timezone.utc) - timedelta(hours=1)
        with self.assertRaises(VideoForbiddenError):
            self.service.create_join_session(self.appointment.id, self.patient)


if __name__ == "__main__":
    unittest.main()
