import unittest
import uuid
from datetime import date
from types import SimpleNamespace

from app.models import AlcoholLog, HabitType
from app.services.alcohol_service import AlcoholService
from app.services.habit_units import canonical_unit, exercise_minutes_per_week


class FakeAlcoholRepository:
    def __init__(self):
        self.rows = []

    def create(self, row):
        self.rows.append(row)
        return row

    def list_history(self, patient_id, cursor, limit):
        return [], None


class FakeProfiles:
    def __init__(self, profile):
        self.profile = profile

    def get_patient(self, user_id):
        return self.profile if user_id == self.profile.user_id else None


class AlcoholAndHabitUnitTests(unittest.TestCase):
    def test_alcohol_model_has_range_and_coherence_checks(self):
        names = {constraint.name for constraint in AlcoholLog.__table__.constraints}
        self.assertTrue({"ck_alcohol_frequency_range", "ck_alcohol_quantity_range",
                         "ck_alcohol_binge_range", "ck_alcohol_response_coherence"} <= names)

    def test_alcohol_is_not_a_habit_type(self):
        self.assertNotIn("ALCOHOL", HabitType.__members__)

    def test_units_are_canonical_and_daily_exercise_is_converted(self):
        self.assertEqual(canonical_unit(HabitType.TOBACCO, "cigarrillos/dia"), "cigarrillos/dia")
        self.assertEqual(exercise_minutes_per_week(30, "min/dia"), 210)
        with self.assertRaises(ValueError):
            canonical_unit(HabitType.TOBACCO, "cigarrillos/semana")

    def test_alcohol_service_enforces_response_coherence_and_ranges(self):
        patient_id = uuid.uuid4()
        repository = FakeAlcoholRepository()
        service = AlcoholService(
            repository,
            FakeProfiles(SimpleNamespace(id=patient_id, user_id=patient_id)),
        )
        with self.assertRaises(ValueError):
            service.create(patient_id, 0, 1, None)
        with self.assertRaises(ValueError):
            service.create(patient_id, 5, None, None)
        row = service.create(patient_id, 2, 1, 3, date(2026, 1, 1))
        self.assertEqual(row.date, date(2026, 1, 1))
        self.assertEqual(repository.rows, [row])


if __name__ == "__main__":
    unittest.main()
