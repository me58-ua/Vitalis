import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import patient_health_profile as module
from app.api.deps import get_appointment_repository, get_current_patient, get_profile_repository, get_audit_repository, get_notification_service
from app.database import get_db
from app.models import Allergy


class PatientHealthProfileTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), role='patient')
        self.profile = SimpleNamespace(id=uuid4(), user_id=self.user.id, share_health_data=False,
            ai_processing_consent=True, onboarding_state={'chat_v1': {'answers': [
                {'question_id': 'allergies', 'extracted': {'status': 'none'}}]}},
            height_cm=178, weight_kg=74, blood_type=None, family_history_reviewed=False,
            onboarding_completed=True)
        self.profiles = Mock()
        self.profiles.get_patient.return_value = self.profile
        self.profiles.list_health_records.return_value = {'allergies': [], 'chronic_conditions': [],
            'medications': [], 'habit_logs': [], 'family_history_entries': []}
        self.profiles.list_alcohol_logs.return_value = []
        self.app = FastAPI()
        self.app.include_router(module.router)
        self.app.dependency_overrides[get_current_patient] = lambda: self.user
        self.app.dependency_overrides[get_profile_repository] = lambda: self.profiles
        self.appointments = Mock()
        self.appointments.patient_follow_ups.return_value = []
        self.app.dependency_overrides[get_appointment_repository] = lambda: self.appointments
        self.app.dependency_overrides[get_audit_repository] = lambda: Mock()
        self.app.dependency_overrides[get_notification_service] = lambda: Mock()
        self.app.dependency_overrides[get_db] = lambda: Mock()
        self.http = TestClient(self.app)
        self.addCleanup(patch.stopall)

    def test_patient_can_read_own_data_without_professional_sharing(self):
        response = self.http.get('/patients/me/health-profile')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['profile']['height_cm'], 178)
        self.assertEqual(response.json()['declarations']['allergies'], 'none')
        self.profiles.list_health_records.assert_called_once_with(self.profile.id)
        self.appointments.patient_follow_ups.assert_called_once_with(self.user.id)
        self.assertEqual(response.json()['appointment_follow_ups'], [])
        self.assertNotIn('answers', response.json())

    def test_read_requires_patient_session(self):
        self.app.dependency_overrides.pop(get_current_patient)
        self.assertEqual(self.http.get('/patients/me/health-profile').status_code, 401)

    def test_health_profile_is_read_only(self):
        for method, path, body in [
            ('patch', '/patients/me/health-profile/biometrics', {'height_cm': 180}),
            ('put', '/patients/me/health-profile/records', {'kind': 'allergy', 'name': 'Test', 'severity': 'leve'}),
            ('delete', '/patients/me/health-profile/records/allergy/1', None),
        ]:
            response = self.http.request(method, path, json=body)
            self.assertIn(response.status_code, (404, 405))
        self.profiles.update.assert_not_called()
        self.profiles.add_health_record.assert_not_called()
        self.profiles.delete_health_record.assert_not_called()


if __name__ == '__main__':
    unittest.main()
