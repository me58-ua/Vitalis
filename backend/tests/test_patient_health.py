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

    def get_professional(self, user_id):
        return getattr(self, "professional_profile", None)


class FakeHistoryAppointments:
    def __init__(self, appointments, notes):
        self.appointments = appointments
        self.notes = notes
        self.calls = []

    def list_patient_history(self, patient_id, professional_id):
        self.calls.append(("appointments", patient_id, professional_id))
        return self.appointments

    def list_patient_notes(self, patient_id, professional_id):
        self.calls.append(("notes", patient_id, professional_id))
        return self.notes


class FakeHistoryPrescriptions:
    def __init__(self, prescriptions):
        self.prescriptions = prescriptions
        self.calls = []

    def list_for_patient_and_professional(self, patient_profile_id, professional_profile_id):
        self.calls.append((patient_profile_id, professional_profile_id))
        return self.prescriptions


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

    def test_professional_snapshot_includes_authorized_history(self):
        patient_user_id = uuid.uuid4()
        professional_user_id = uuid.uuid4()
        profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=patient_user_id, share_health_data=True
        )
        repository = FakeProfiles(profile)
        repository.professional_profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=professional_user_id
        )
        appointments = FakeHistoryAppointments(["appointment"], ["note"])
        prescriptions = FakeHistoryPrescriptions(["prescription"])

        result = PatientHealthService(repository, appointments, prescriptions).snapshot_by_user_id(
            patient_user_id, professional_user_id
        )

        self.assertTrue(result["consent_shared"])
        self.assertEqual(result["appointments"], ["appointment"])
        self.assertEqual(result["clinical_notes"], ["note"])
        self.assertEqual(result["prescriptions"], ["prescription"])
        self.assertEqual(appointments.calls[0][1:], (patient_user_id, professional_user_id))
        self.assertEqual(
            prescriptions.calls[0], (profile.id, repository.professional_profile.id)
        )

    def test_professional_snapshot_does_not_query_history_without_consent(self):
        patient_user_id = uuid.uuid4()
        profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=patient_user_id, share_health_data=False
        )
        repository = FakeProfiles(profile)
        appointments = FakeHistoryAppointments([], [])
        prescriptions = FakeHistoryPrescriptions([])

        result = PatientHealthService(repository, appointments, prescriptions).snapshot_by_user_id(
            patient_user_id, uuid.uuid4()
        )

        self.assertFalse(result["consent_shared"])
        self.assertEqual(appointments.calls, [])
        self.assertEqual(prescriptions.calls, [])


if __name__ == "__main__":
    unittest.main()