import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from app.models import AllergySeverity, HabitType
from app.services.patient_health_service import PatientHealthService, PatientHistoryAccessError


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

    def has_shared_appointment(self, patient_id, professional_id):
        self.calls.append(("shared", patient_id, professional_id))
        return True

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

    def test_onboarding_without_ai_provider_skips_block_without_saving(self):
        profile = SimpleNamespace(id=uuid.uuid4(), onboarding_completed=False)
        repository = FakeProfiles(profile)
        completed, saved, question = PatientHealthService(repository).save_onboarding_message(
            profile, "alergias", "Penicilina"
        )
        self.assertFalse(saved)
        self.assertFalse(completed)
        self.assertTrue(question)
        self.assertEqual(repository.records, [])

    def test_onboarding_without_ai_consent_skips_without_calling_llm(self):
        profile = SimpleNamespace(
            id=uuid.uuid4(), onboarding_completed=False, ai_processing_consent=False
        )
        repository = FakeProfiles(profile)
        service = PatientHealthService(repository)
        service._extract = Mock(side_effect=AssertionError("LLM must not be called"))

        completed, saved, message = service.save_onboarding_message(
            profile, "alergias", "Penicilina"
        )

        self.assertTrue(completed)
        self.assertFalse(saved)
        self.assertEqual(repository.records, [])
        self.assertEqual(message, "AI_CONSENT_REQUIRED")
        service._extract.assert_not_called()

    def test_onboarding_can_resume_after_ai_consent(self):
        profile = SimpleNamespace(
            id=uuid.uuid4(), onboarding_completed=True, ai_processing_consent=False
        )
        repository = FakeProfiles(profile)
        service = PatientHealthService(repository)

        self.assertFalse(service.resume(profile))
        profile.ai_processing_consent = True
        self.assertTrue(service.resume(profile))
        self.assertFalse(profile.onboarding_completed)

    def test_resume_exposes_persisted_question_and_pending_family_confirmation(self):
        profile = SimpleNamespace(
            id=uuid.uuid4(),
            onboarding_completed=True,
            ai_processing_consent=True,
            onboarding_state={
                "last_question_id": "family_history",
                "family_history": {"status": "entries", "entries": []},
            },
        )
        resumed, next_question, last_question, pending = PatientHealthService(
            FakeProfiles(profile)
        ).resume_state(profile)

        self.assertTrue(resumed)
        self.assertEqual(next_question, "family_history_confirmation")
        self.assertEqual(last_question, "family_history")
        self.assertTrue(pending)

    def test_audit_c_answers_persist_until_complete(self):
        profile = SimpleNamespace(
            id=uuid.uuid4(), onboarding_completed=False, ai_processing_consent=True
        )
        repository = FakeProfiles(profile)
        service = PatientHealthService(repository)
        service._extract = Mock(
            side_effect=[
                {"frequency": 2},
                {"quantity": 1},
                {"binge": 0},
            ]
        )

        service.save_onboarding_message(profile, "alcohol", "dos", "auditc_frequency")
        service.save_onboarding_message(profile, "alcohol", "uno", "auditc_quantity")
        _, saved, _ = service.save_onboarding_message(
            profile, "alcohol", "nunca", "auditc_binge"
        )

        self.assertTrue(saved)
        self.assertEqual(len(repository.records), 1)
        self.assertEqual(repository.records[0].frequency, 2)
        self.assertNotIn("audit_c", profile.onboarding_state)

    def test_family_history_confirmation_persists_only_after_confirmation(self):
        profile = SimpleNamespace(
            id=uuid.uuid4(),
            onboarding_state={
                "family_history": {
                    "status": "entries",
                    "entries": [
                        {
                            "relationship": "madre",
                            "category": "diabetes",
                            "detail": None,
                            "age": 60,
                        }
                    ],
                }
            },
            family_history_reviewed=False,
        )
        repository = FakeProfiles(profile)
        family_service = Mock()

        confirmed = PatientHealthService(
            repository, family_history_service=family_service
        ).confirm_family_history(profile, SimpleNamespace(), True)

        self.assertTrue(confirmed)
        self.assertTrue(profile.family_history_reviewed)
        family_service.create_from_onboarding.assert_called_once()
        self.assertNotIn("family_history", profile.onboarding_state)

    def test_onboarding_completes_after_habits_block(self):
        profile = SimpleNamespace(id=uuid.uuid4(), onboarding_completed=False)
        repository = FakeProfiles(profile)
        completed, saved, _ = PatientHealthService(repository).save_onboarding_message(
            profile, "habitos", "7 horas"
        )
        self.assertTrue(completed)
        self.assertFalse(saved)
        self.assertEqual(repository.records, [])

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
        documents = Mock()
        documents.list_for_patient.return_value = ["document"]

        result = PatientHealthService(
            repository, appointments, prescriptions, health_documents=documents
        ).snapshot_by_user_id(patient_user_id, professional_user_id)

        self.assertTrue(result["consent_shared"])
        self.assertEqual(result["appointments"], ["appointment"])
        self.assertEqual(result["clinical_notes"], ["note"])
        self.assertEqual(result["prescriptions"], ["prescription"])
        self.assertEqual(result["health_documents"], ["document"])
        documents.list_for_patient.assert_called_once_with(profile.id)
        self.assertEqual(appointments.calls[0][1:], (patient_user_id, professional_user_id))
        self.assertEqual(
            prescriptions.calls[0], (profile.id, repository.professional_profile.id)
        )

    def test_professional_snapshot_keeps_own_history_without_patient_consent(self):
        patient_user_id = uuid.uuid4()
        profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=patient_user_id, share_health_data=False
        )
        repository = FakeProfiles(profile)
        repository.professional_profile = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
        appointments = FakeHistoryAppointments(["appointment"], ["note"])
        prescriptions = FakeHistoryPrescriptions(["prescription"])

        result = PatientHealthService(repository, appointments, prescriptions).snapshot_by_user_id(
            patient_user_id, repository.professional_profile.user_id
        )

        self.assertFalse(result["consent_shared"])
        self.assertEqual(result["appointments"], ["appointment"])
        self.assertEqual(result["clinical_notes"], ["note"])
        self.assertEqual(result["prescriptions"], ["prescription"])
        self.assertNotIn("allergies", result)
        self.assertNotIn("health_documents", result)

    def test_professional_without_shared_appointment_cannot_access_history(self):
        patient_user_id = uuid.uuid4()
        profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=patient_user_id, share_health_data=True
        )
        repository = FakeProfiles(profile)
        repository.professional_profile = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
        appointments = FakeHistoryAppointments([], [])
        appointments.has_shared_appointment = lambda patient_id, professional_id: False

        with self.assertRaises(PatientHistoryAccessError):
            PatientHealthService(
                repository, appointments, FakeHistoryPrescriptions([])
            ).snapshot_by_user_id(patient_user_id, repository.professional_profile.user_id)


if __name__ == "__main__":
    unittest.main()