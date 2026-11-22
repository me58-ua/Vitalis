import unittest
from types import SimpleNamespace
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.video import router
from app.api.deps import get_current_user, get_appointment_repository, get_video_session_repository, get_audit_repository
from app.models import UserRole
from tests.test_video import FakeAppointmentRepository, FakeEventRepository


class PatientVideoApiTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), role=UserRole.PATIENT, is_active=True)
        self.calls = []
        class Repository:
            def list_patient_appointments(inner, patient_id, offset, limit, confirmed_only=False):
                self.calls.append((patient_id, offset, limit))
                return [], 0
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_appointment_repository] = lambda: Repository()
        self.app.dependency_overrides[get_video_session_repository] = lambda: FakeEventRepository()
        self.app.dependency_overrides[get_audit_repository] = lambda: None
        self.client = TestClient(self.app)

    def test_patient_listing_is_scoped_to_authenticated_identity_and_paginated(self):
        response = self.client.get('/patients/me/appointments?page=2&page_size=5')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, [(self.user.id, 5, 5)])
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.json(), {'appointments': [], 'total': 0, 'page': 2, 'page_size': 5})

    def test_professional_cannot_use_patient_listing(self):
        self.user.role = UserRole.PROFESSIONAL
        self.assertEqual(self.client.get('/patients/me/appointments').status_code, 403)
        self.assertEqual(self.calls, [])

    def test_invalid_pagination_and_attendance_are_rejected(self):
        for query in ('page=0', 'page_size=101'):
            self.assertEqual(self.client.get('/patients/me/appointments?' + query).status_code, 422)
        response = self.client.post(f'/appointments/{uuid4()}/video/attendance', json={'event': 'completed'})
        self.assertEqual(response.status_code, 422)

    def test_unknown_appointment_is_not_found(self):
        self.app.dependency_overrides[get_appointment_repository] = lambda: FakeAppointmentRepository(SimpleNamespace(id=uuid4()))
        response = self.client.post(f'/appointments/{uuid4()}/video/attendance', json={'event': 'joined'})
        self.assertEqual(response.status_code, 404)
