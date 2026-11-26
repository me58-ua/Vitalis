import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import settings
from app.models import AppointmentStatus, AppointmentType, UserRole
from app.services.daily_client import DailyClient, DailyUnavailableError
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

    def lock_overdue_unattended_video(self, cutoff):
        appointment = self.appointment
        if (appointment.type == AppointmentType.VIDEO
                and appointment.status == AppointmentStatus.CONFIRMED
                and appointment.start_time <= cutoff):
            return [appointment]
        return []


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
            DAILY_API_KEY="test-secret",
            DAILY_TOKEN_TTL_SECONDS=3600,
            VIDEO_JOIN_EARLY_MINUTES=10,
        )
        self.config.start()
        daily = patch("app.services.daily_client.DailyClient._request", side_effect=self.daily_request)
        self.daily = daily.start()
        self.addCleanup(daily.stop)
        self.rooms = {}

    def daily_request(self, path, payload=None, *, missing_ok=False):
        if path == "/rooms":
            name = payload["name"]
            self.rooms[name] = {"privacy": payload["privacy"], "url": f"https://vitalis-test.daily.co/{name}"}
            return self.rooms[name]
        if path == "/meeting-tokens":
            return {"token": "test-daily-token"}
        return self.rooms.get(path.removeprefix("/rooms/"))

    def tearDown(self):
        self.config.stop()

    def test_participant_gets_valid_token_and_room_is_stable(self):
        first = self.service.create_join_session(self.appointment.id, self.patient)
        second = self.service.create_join_session(self.appointment.id, self.patient)
        self.assertEqual(first["room_url"], second["room_url"])
        self.assertEqual(first["token"], "test-daily-token")
        self.assertEqual(len(self.rooms), 1)
        room = f"vitalis-{self.appointment.id.hex}"
        self.assertEqual(self.rooms[room]["privacy"], "private")
        token = self.daily.call_args.args[1]["properties"]
        self.assertEqual(token["room_name"], room)
        self.assertEqual(token["user_id"], str(self.patient.id))
        self.assertFalse(token["is_owner"])
        self.assertEqual(len(self.events.events), 2)

    def test_only_professional_gets_owner_token(self):
        self.service.create_join_session(self.appointment.id, self.professional)
        self.assertTrue(self.daily.call_args.args[1]["properties"]["is_owner"])

    def test_concurrent_room_creation_reuses_the_room_created_by_the_other_request(self):
        url = "https://vitalis-test.daily.co/example"
        self.daily.side_effect = [None, DailyUnavailableError(), {"privacy": "private", "url": url}]
        self.assertEqual(DailyClient("test-secret").get_or_create_room("example"), url)
        self.assertEqual(self.daily.call_args.args[0], "/rooms/example")

    def test_daily_failure_does_not_record_access(self):
        self.daily.side_effect = DailyUnavailableError()
        with self.assertRaises(DailyUnavailableError):
            self.service.create_join_session(self.appointment.id, self.patient)
        self.assertEqual(self.events.events, [])

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
        self.assertIn('token', self.service.create_join_session(self.appointment.id, self.patient))

    def test_join_grace_period_ends_after_one_hour_unless_professional_attended(self):
        self.appointment.start_time = datetime.now(timezone.utc) - timedelta(minutes=59)
        self.service.create_join_session(self.appointment.id, self.professional)
        self.appointment.start_time -= timedelta(minutes=2)
        with self.assertRaises(VideoForbiddenError):
            self.service.create_join_session(self.appointment.id, self.patient)
        with self.assertRaises(VideoForbiddenError):
            self.service.record_attendance(self.appointment.id, self.professional, 'joined')
        self.appointment.start_time += timedelta(minutes=2)
        self.service.record_attendance(self.appointment.id, self.professional, 'joined')
        self.appointment.start_time -= timedelta(minutes=2)
        self.assertIn('token', self.service.create_join_session(self.appointment.id, self.patient))
        self.assertEqual(self.service.expire_professional_no_shows(), 0)

    def test_completed_cancelled_and_no_show_appointments_cannot_join(self):
        for status in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW,
                       AppointmentStatus.NO_SHOW_PROFESSIONAL):
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

    def test_patient_departure_without_professional_attendance_expires_and_audits_once(self):
        audits = Mock()
        service = VideoService(self.service.appointments, self.events, audits)
        for user in (self.patient, self.professional):
            service.create_join_session(self.appointment.id, user)
        service.record_attendance(self.appointment.id, self.patient, 'joined')
        self.assertEqual(service.record_attendance(self.appointment.id, self.patient, 'left')['status'],
                         AppointmentStatus.CONFIRMED)
        deadline = self.appointment.start_time + timedelta(hours=1)
        self.assertEqual(service.expire_professional_no_shows(deadline - timedelta(microseconds=1)), 0)
        self.assertEqual(service.expire_professional_no_shows(deadline), 1)
        self.assertEqual(service.expire_professional_no_shows(deadline), 0)
        self.assertEqual(self.appointment.status, AppointmentStatus.NO_SHOW_PROFESSIONAL)
        history, = service.appointments.history
        self.assertIsNone(history.changed_by)
        self.assertEqual(history.new_status, AppointmentStatus.NO_SHOW_PROFESSIONAL)
        audits.create.assert_called_once()
        log = audits.create.call_args.args[0]
        self.assertIsNone(log.actor_id)
        self.assertEqual((log.entidad, log.entidad_id), ("appointment_professional_no_show", self.appointment.id))

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
