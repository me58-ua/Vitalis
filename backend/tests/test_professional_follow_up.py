import unittest
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.models import AppointmentStatus, AppointmentType, UserRole
from app.services.appointment_service import AppointmentAccessError
from app.services.professional_follow_up_service import ProfessionalFollowUpService


class FakeAppointments:
    def __init__(self):
        self.past_calls = []
        self.records = []
        self.total = 0

    def list_past_for_professional(self, *args):
        self.past_calls.append(args)
        return self.records, self.total


class FakePrescriptions:
    def __init__(self):
        self.calls = []
        self.records = []
        self.total = 0

    def list_for_professional(self, *args):
        self.calls.append(args)
        return self.records, self.total


class FakeProfiles:
    def __init__(self, professional_profile):
        self.professional_profile = professional_profile

    def get_professional(self, user_id):
        return self.professional_profile if user_id == self.professional_profile.user_id else None


class ProfessionalFollowUpServiceTests(unittest.TestCase):
    def setUp(self):
        self.professional_id = uuid.uuid4()
        self.patient_id = uuid.uuid4()
        self.patient = SimpleNamespace(
            id=self.patient_id,
            name="Ana Patient",
            username="ana.patient",
            email="ana@example.com",
        )
        self.appointment = SimpleNamespace(
            id=uuid.uuid4(),
            patient_id=self.patient_id,
            professional_id=self.professional_id,
            start_time=datetime(2026, 9, 20, 10, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 20, 11, tzinfo=timezone.utc),
            status=AppointmentStatus.COMPLETED,
            type=AppointmentType.VIDEO,
            reason="Follow-up",
            room_id=uuid.uuid4(),
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 20, 11, tzinfo=timezone.utc),
        )
        self.appointments = FakeAppointments()
        self.note = SimpleNamespace(
            clinical_notes="Clinical follow-up",
            patient_summary="Patient is improving",
            diagnosis="Stable condition",
        )
        self.appointments.records = [(self.appointment, self.patient, self.note)]
        self.appointments.total = 1
        self.prescriptions = FakePrescriptions()
        self.prescriptions.records = [SimpleNamespace(
            id=uuid.uuid4(),
            appointment_id=self.appointment.id,
            patient_id=uuid.uuid4(),
            professional_id=uuid.uuid4(),
            file_url="prescriptions/test.pdf",
            notas=None,
            created_at=datetime(2026, 9, 20, 11, tzinfo=timezone.utc),
        )]
        self.prescriptions.total = 1
        self.professional_profile = SimpleNamespace(id=uuid.uuid4(), user_id=self.professional_id)
        self.profiles = FakeProfiles(self.professional_profile)
        self.current_user = SimpleNamespace(id=self.professional_id, role=UserRole.PROFESSIONAL)
        self.service = ProfessionalFollowUpService(
            self.appointments,
            self.prescriptions,
            self.profiles,
            now=lambda: datetime(2026, 9, 29, tzinfo=timezone.utc),
        )

    def test_lists_past_appointments_with_combined_filters(self):
        result = self.service.list_past_appointments(
            self.professional_id,
            self.current_user,
            self.patient_id,
            "Ana",
            date(2026, 9, 1),
            date(2026, 9, 30),
            AppointmentStatus.COMPLETED,
            page=2,
            page_size=10,
        )

        call = self.appointments.past_calls[0]
        self.assertEqual(call[0], self.professional_id)
        self.assertEqual(call[2:7], (
            self.patient_id,
            "Ana",
            datetime(2026, 9, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            AppointmentStatus.COMPLETED,
        ))
        self.assertEqual(call[7:], (10, 10))
        self.assertEqual(result.total, 1)
        self.assertEqual(result.appointments[0].patient_name, "Ana Patient")
        self.assertEqual(result.appointments[0].diagnosis, "Stable condition")

    def test_rejects_different_professional(self):
        with self.assertRaises(AppointmentAccessError):
            self.service.list_past_appointments(
                uuid.uuid4(), self.current_user, None, None, None, None, None, 1, 20
            )

    def test_rejects_reversed_date_range(self):
        with self.assertRaises(ValueError):
            self.service.list_past_appointments(
                self.professional_id,
                self.current_user,
                None,
                None,
                date(2026, 9, 30),
                date(2026, 9, 1),
                None,
                1,
                20,
            )

    def test_lists_professional_prescriptions_by_patient_and_date(self):
        result = self.service.list_prescriptions(
            self.professional_id,
            self.current_user,
            self.patient_id,
            date(2026, 9, 1),
            date(2026, 9, 30),
            page=1,
            page_size=5,
        )

        call = self.prescriptions.calls[0]
        self.assertEqual(call[0], self.professional_profile.id)
        self.assertEqual(call[1], self.patient_id)
        self.assertEqual(call[2], datetime(2026, 9, 1, tzinfo=timezone.utc))
        self.assertEqual(call[3], datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(call[4:], (0, 5))
        self.assertEqual(result.total, 1)

    def test_empty_patient_prescription_list_returns_message(self):
        self.prescriptions.records = []
        self.prescriptions.total = 0

        result = self.service.list_prescriptions(
            self.professional_id,
            self.current_user,
            self.patient_id,
            None,
            None,
            page=1,
            page_size=5,
        )

        self.assertEqual(result.message, "No se encontraron recetas para este paciente")


if __name__ == "__main__":
    unittest.main()