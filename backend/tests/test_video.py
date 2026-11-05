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
        self.history = []

    def get_appointment(self, appointment_id):
        return self.appointment if self.appointment.id == appointment_id else None

    def save(self, appointment):
        return appointment

    def lock_appointment(self, appointment_id):
        return self.get_appointment(appointment_id)

    def create_status_history(self, history):
        self.history.append(history)


class FakeEventRepository:
    def __init__(self):
        self.events = []

    def create(self, event):
        self.events.append(event)
        return event

    def has_event(self, appointment_id, user_id, event):
        return any(item.appointment_id == appointment_id and item.user_id == user_id and item.event == event for item in self.events)


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
            JITSI_XMPP_DOMAIN="meet.jitsi",
            JITSI_APP_ID="vitalis",
            JITSI_APP_SECRET="test-secret",
            JITSI_TOKEN_TTL_SECONDS=3600,
            VIDEO_JOIN_EARLY_MINUTES=10,
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
        self.assertEqual(claims["sub"], "meet.jitsi")
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

    def test_join_more_than_ten_minutes_early_is_rejected(self):
        self.appointment.start_time = datetime.now(timezone.utc) + timedelta(minutes=11)
        self.appointment.end_time = self.appointment.start_time + timedelta(minutes=30)
        with self.assertRaises(VideoForbiddenError):
            self.service.create_join_session(self.appointment.id, self.patient)

    def test_join_inside_early_window_is_allowed(self):
        self.appointment.start_time = datetime.now(timezone.utc) + timedelta(minutes=9)
        self.appointment.end_time = self.appointment.start_time + timedelta(minutes=30)
        self.assertIn('jwt', self.service.create_join_session(self.appointment.id, self.patient))

    def test_late_join_is_allowed_and_token_still_has_a_finite_lifetime(self):
        for age in (timedelta(hours=8), timedelta(days=40)):
            self.appointment.start_time = datetime.now(timezone.utc) - age
            self.appointment.end_time = self.appointment.start_time + timedelta(minutes=30)
            result = self.service.create_join_session(self.appointment.id, self.patient)
            self.assertGreater(result['expires_at'], datetime.now(timezone.utc))
            self.assertLessEqual(result['expires_at'], datetime.now(timezone.utc) + timedelta(seconds=3600))

    def test_completed_cancelled_and_no_show_appointments_cannot_join(self):
        for status in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
            self.appointment.status = status
            with self.assertRaises(VideoForbiddenError):
                self.service.create_join_session(self.appointment.id, self.patient)

    def test_token_or_loading_alone_does_not_complete_appointment(self):
        self.service.create_join_session(self.appointment.id, self.patient)
        with self.assertRaises(VideoForbiddenError):
            self.service.record_attendance(self.appointment.id, self.patient, 'left')
        self.assertEqual(self.appointment.status, AppointmentStatus.CONFIRMED)

    def test_joined_requires_previously_issued_access(self):
        with self.assertRaises(VideoForbiddenError):
            self.service.record_attendance(self.appointment.id, self.patient, 'joined')

    def test_patient_departure_completes_once_and_professional_can_leave_independently(self):
        for user in (self.patient, self.professional):
            self.service.create_join_session(self.appointment.id, user)
            self.service.record_attendance(self.appointment.id, user, 'joined')
        result = self.service.record_attendance(self.appointment.id, self.patient, 'left')
        self.assertEqual(result['status'], AppointmentStatus.COMPLETED)
        self.assertFalse(self.events.has_event(self.appointment.id, self.professional.id, 'left'))
        self.service.record_attendance(self.appointment.id, self.patient, 'left')
        self.service.record_attendance(self.appointment.id, self.professional, 'left')
        self.assertEqual(len(self.service.appointments.history), 1)
        self.assertEqual(self.service.appointments.history[0].changed_by, self.patient.id)
        self.assertEqual(sum(item.event == 'left' for item in self.events.events), 2)

    def test_professional_can_finish_first_without_marking_patient_departed(self):
        self.service.create_join_session(self.appointment.id, self.professional)
        self.service.record_attendance(self.appointment.id, self.professional, 'joined')
        self.service.record_attendance(self.appointment.id, self.professional, 'left')
        self.assertEqual(self.appointment.status, AppointmentStatus.COMPLETED)
        self.assertFalse(self.events.has_event(self.appointment.id, self.patient.id, 'left'))

    def test_third_party_and_inactive_user_cannot_report_attendance(self):
        outsider = SimpleNamespace(id=uuid.uuid4(), is_active=True)
        for user in (outsider, SimpleNamespace(id=self.patient.id, is_active=False)):
            with self.assertRaises(VideoForbiddenError):
                self.service.record_attendance(self.appointment.id, user, 'joined')

    def test_cancelled_or_non_video_cannot_be_completed_by_departure(self):
        self.service.create_join_session(self.appointment.id, self.patient)
        self.service.record_attendance(self.appointment.id, self.patient, 'joined')
        self.appointment.status = AppointmentStatus.CANCELLED
        with self.assertRaises(VideoForbiddenError):
            self.service.record_attendance(self.appointment.id, self.patient, 'left')
        self.appointment.status = AppointmentStatus.CONFIRMED
        self.appointment.type = AppointmentType.IN_PERSON
        with self.assertRaises(VideoForbiddenError):
            self.service.record_attendance(self.appointment.id, self.patient, 'left')


if __name__ == "__main__":
    unittest.main()
