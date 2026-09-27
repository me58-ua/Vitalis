import unittest
import uuid
from types import SimpleNamespace

from app.models import AllergySeverity, HabitType
from app.services.patient_health_service import PatientHealthService


class FakeSession:
    def flush(self):
        pass


class FakeProfiles:
    def __init__(self, profile):
        self.profile = profile
        self.session = FakeSession()
        self.records = []

    def add_health_record(self, record):
        self.records.append(record)
        return record

    def list_health_records(self, profile_id):
        return {"allergies": [], "chronic_conditions": [], "medications": [], "habit_logs": []}

    def get_patient(self, user_id):
        return self.profile


class PatientHealthTests(unittest.TestCase):
    def test_consent_false_hides_all_health_sections(self):
        profile = SimpleNamespace(id=uuid.uuid4(), share_health_data=False)
        result = PatientHealthService(FakeProfiles(profile)).snapshot(profile)
        self.assertFalse(result["consent_shared"])
        self.assertNotIn("allergies", result)

    def test_onboarding_fallback_saves_structured_allergy_without_raw_message(self):
        profile = SimpleNamespace(id=uuid.uuid4(), onboarding_completed=False)
        repository = FakeProfiles(profile)
        completed, saved, question = PatientHealthService(repository).save_onboarding_message(
            profile, "alergias", "Penicilina"
        )
        self.assertTrue(saved)
        self.assertFalse(completed)
        self.assertTrue(question)
        self.assertEqual(len(repository.records), 1)
        self.assertEqual(repository.records[0].name, "Penicilina")
        self.assertEqual(repository.records[0].severity, AllergySeverity.MILD.value)
        self.assertFalse(hasattr(repository.records[0], "message"))

    def test_onboarding_completes_after_habits_block(self):
        profile = SimpleNamespace(id=uuid.uuid4(), onboarding_completed=False)
        repository = FakeProfiles(profile)
        completed, saved, _ = PatientHealthService(repository).save_onboarding_message(
            profile, "habitos", "7 horas"
        )
        self.assertTrue(completed)
        self.assertTrue(saved)
        self.assertEqual(repository.records[0].habit_type, HabitType.DIET.value)


if __name__ == "__main__":
    unittest.main()