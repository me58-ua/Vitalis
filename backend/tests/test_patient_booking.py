import unittest
import uuid
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.models import AppointmentStatus, AppointmentType, UserRole
from app.schemas.appointments import PatientAppointmentCreate
from app.services.appointment_service import AppointmentService, AppointmentValidationError


class FakeSession:
    def flush(self):
        pass


class FakeAppointments:
    def __init__(self, schedules, booked=None):
        self.schedules = schedules
        self.booked = booked or []
        self.created = []
        self.session = FakeSession()

    def list_active_schedules(self, professional_id, day_of_week, channel):
        return [schedule for schedule in self.schedules if schedule.day_of_week == day_of_week and schedule.channel == channel]

    def list_booked_appointments(self, professional_id, start, end):
        return [
            appointment for appointment in self.booked
            if appointment.start_time < end and appointment.end_time > start
        ]

    def create_appointment(self, appointment):
        self.created.append(appointment)
        return appointment


class FakeProfessionals:
    def __init__(self, professional_id):
        self.professional_id = professional_id
        self.profile = SimpleNamespace(
            is_accepting_new_patients=True,
            telehealth_enabled=True,
        )

    def get_professional(self, professional_id):
        if professional_id != self.professional_id:
            return None
        return SimpleNamespace(id=professional_id), self.profile


class FakeUsers:
    def get_by_id(self, user_id):
        return SimpleNamespace(id=user_id, role=UserRole.PATIENT)


class PatientBookingTests(unittest.TestCase):
    def test_pending_is_no_longer_an_appointment_status(self):
        with self.assertRaises(ValueError):
            AppointmentStatus('pending')

    def setUp(self):
        self.professional_id = uuid.uuid4()
        self.patient_id = uuid.uuid4()
        self.requested_date = date(2026, 9, 28)
        self.schedule = SimpleNamespace(
            channel="video",
            day_of_week=self.requested_date.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
            slot_duration_min=30,
        )
        self.appointments = FakeAppointments([self.schedule])
        self.service = AppointmentService(
            self.appointments,
            FakeUsers(),
            FakeProfessionals(self.professional_id),
        )

    def test_slots_are_generated_and_booked_slot_is_excluded(self):
        booked_start = datetime(2026, 9, 28, 9, 30, tzinfo=ZoneInfo("Europe/Madrid"))
        self.appointments.booked = [
            SimpleNamespace(
                start_time=booked_start,
                end_time=booked_start + timedelta(minutes=30),
                status=AppointmentStatus.CONFIRMED,
            )
        ]
        slots = self.service.list_available_slots(
            self.professional_id, self.requested_date, AppointmentType.VIDEO
        )
        self.assertEqual(len(slots), 3)
        self.assertNotIn((booked_start, booked_start + timedelta(minutes=30)), slots)

    def test_patient_can_book_only_an_available_slot(self):
        start = datetime(2026, 9, 28, 9, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        data = PatientAppointmentCreate(
            professional_id=self.professional_id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            type=AppointmentType.VIDEO,
        )
        appointment = self.service.create_for_patient(
            SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT), data
        )
        self.assertEqual(appointment.patient_id, self.patient_id)
        self.assertEqual(appointment.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(len(self.appointments.created), 1)

    def test_each_modality_uses_only_its_own_schedule(self):
        get_slots = lambda modality: self.service.list_available_slots(self.professional_id, self.requested_date, modality)
        self.assertEqual(get_slots(AppointmentType.IN_PERSON), [])
        self.appointments.schedules.append(SimpleNamespace(
            **(vars(self.schedule) | {"channel": "in_person", "start_time": time(14), "end_time": time(15)}),
        ))
        self.assertEqual([start.hour for start, _ in get_slots(AppointmentType.IN_PERSON)], [14, 14])
        self.assertEqual([start.hour for start, _ in get_slots(AppointmentType.VIDEO)], [9, 9, 10, 10])
        start, end = get_slots(AppointmentType.IN_PERSON)[0]
        with self.assertRaisesRegex(AppointmentValidationError, "not an available slot"):
            self.service.create_for_patient(
                SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT),
                PatientAppointmentCreate(professional_id=self.professional_id, start_time=start, end_time=end, type=AppointmentType.VIDEO),
            )

    def test_patient_cannot_book_arbitrary_time(self):
        start = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)
        data = PatientAppointmentCreate(
            professional_id=self.professional_id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            type=AppointmentType.VIDEO,
        )
        with self.assertRaises(AppointmentValidationError):
            self.service.create_for_patient(
                SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT), data
            )


if __name__ == "__main__":
    unittest.main()
