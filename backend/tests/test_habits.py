import unittest
import uuid
from datetime import date
from types import SimpleNamespace

from app.models import HabitType, UserRole
from app.services.habit_service import HabitAccessError, HabitService, HabitValidationError


class FakeHabits:
    def __init__(self):
        self.list_calls = []
        self.aggregate_calls = []

    def list_filtered(self, *args):
        self.list_calls.append(args)
        return [SimpleNamespace(id=1)], 3

    def aggregate(self, *args):
        self.aggregate_calls.append(args)
        return [{"habit_type": HabitType.EXERCISE, "count": 2, "numeric_count": 2, "sum": 90, "average": 45, "minimum": 30, "maximum": 60}]


class FakeProfiles:
    def __init__(self, profile):
        self.profile = profile

    def get_patient(self, user_id):
        return self.profile if user_id == self.profile.user_id else None


class FakeAppointments:
    def __init__(self, shared=True):
        self.shared = shared

    def health_sharing_scope(self, profile, professional_id):
        return "full" if self.shared and profile.share_health_data else "none"


class HabitServiceTests(unittest.TestCase):
    def setUp(self):
        self.patient_user_id = uuid.uuid4()
        self.professional_user_id = uuid.uuid4()
        self.profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=self.patient_user_id, share_health_data=True
        )
        self.habits = FakeHabits()
        self.appointments = FakeAppointments()
        self.service = HabitService(self.habits, FakeProfiles(self.profile), self.appointments)
        self.patient = SimpleNamespace(id=self.patient_user_id, role=UserRole.PATIENT)

    def test_patient_history_passes_filters_pagination_and_aggregates(self):
        result = self.service.list_for_patient(
            self.patient,
            HabitType.EXERCISE,
            "min",
            date(2026, 1, 1),
            date(2026, 1, 31),
            2,
            10,
        )

        expected = (self.profile.id, HabitType.EXERCISE, "min", date(2026, 1, 1), date(2026, 1, 31), 10, 10)
        self.assertEqual(self.habits.list_calls, [expected])
        self.assertEqual(self.habits.aggregate_calls, [expected[:-2]])
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["page"], 2)
        self.assertEqual(result["aggregates"][0]["average"], 45)

    def test_reversed_date_range_is_rejected(self):
        with self.assertRaisesRegex(HabitValidationError, "start_date"):
            self.service.list_for_patient(
                self.patient,
                None,
                None,
                date(2026, 2, 1),
                date(2026, 1, 1),
                1,
                50,
            )

    def test_professional_requires_consent_and_shared_appointment(self):
        with self.assertRaises(HabitAccessError):
            self.profile.share_health_data = False
            self.service.list_for_professional(
                self.patient_user_id, self.professional_user_id, None, None, None, None, 1, 50
            )

        self.profile.share_health_data = True
        self.appointments.shared = False
        with self.assertRaises(HabitAccessError):
            self.service.list_for_professional(
                self.patient_user_id, self.professional_user_id, None, None, None, None, 1, 50
            )

    def test_professional_can_read_consented_history_after_shared_appointment(self):
        result = self.service.list_for_professional(
            self.patient_user_id, self.professional_user_id, HabitType.SLEEP, None, None, None, 1, 25
        )

        self.assertEqual(result["page_size"], 25)
        self.assertEqual(self.habits.list_calls[0][1], HabitType.SLEEP)


if __name__ == "__main__":
    unittest.main()