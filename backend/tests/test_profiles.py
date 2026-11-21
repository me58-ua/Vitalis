import unittest
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException

from app.api.deps import get_current_patient, get_current_professional
from app.api.profiles import (
    change_patient_password,
    get_patient_profile,
    update_ai_consent,
    update_patient_profile,
)
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import hash_password, verify_password
from app.models import UserRole
from app.schemas.profiles import (
    BasicUserUpdate,
    ChangePasswordRequest,
    PatientProfileUpdate,
    ProfessionalProfileUpdate,
)
from app.schemas.health import AIConsentUpdate
from app.services.profile_service import InvalidCurrentPasswordError, ProfileService


class FakeSession:
    def __init__(self):
        self.flush_count = 0
        self.commit_count = 0

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1


class FakeUserRepository:
    def __init__(self, user):
        self.user = user
        self.session = FakeSession()

    def update(self, user, values):
        for field, value in values.items():
            setattr(user, field, value)
        self.session.flush()
        return user


class FakeProfileRepository:
    def __init__(self, patient=None, professional=None):
        self.patient = patient
        self.professional = professional
        self.updated = None
        self.session = FakeSession()

    def get_patient(self, user_id):
        return self.patient if self.patient and self.patient.user_id == user_id else None

    def get_professional(self, user_id):
        return self.professional if self.professional and self.professional.user_id == user_id else None

    def update(self, profile, values):
        for field, value in values.items():
            setattr(profile, field, value)
        self.updated = profile
        return profile


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.PATIENT,
            password_hash=hash_password("OldPassword123!"),
            session_version=0,
            name="Patient",
            email="patient@example.test",
            tel="+34111111111",
            birth_date=None,
            gender=None,
        )
        self.patient_profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=self.user.id, address=None, blood_type=None,
            allergies_summary=None, chronic_conditions_summary=None, timezone="Europe/Madrid",
            ai_processing_consent=False, ai_processing_consent_at=None,
        )
        self.profiles = FakeProfileRepository(patient=self.patient_profile)
        self.users = FakeUserRepository(self.user)
        self.service = ProfileService(self.users, self.profiles)

    def test_patient_profile_update_changes_only_supplied_fields(self):
        result = self.service.update_patient_profile(
            self.user,
            PatientProfileUpdate(timezone="UTC"),
        )

        self.assertEqual(result.timezone, "UTC")
        self.assertIsNone(result.address)
        self.assertEqual(result.timezone, "UTC")

    def test_ai_consent_update_is_owned_by_profile_service_and_records_timestamp(self):
        result = self.service.update_ai_consent(self.user, True)

        self.assertTrue(result.ai_processing_consent)
        self.assertIsInstance(result.ai_processing_consent_at, datetime)
        self.assertFalse(result.ai_consent_required)
        self.assertIsNone(result.ai_consent_code)

    def test_ai_consent_endpoint_returns_not_found_without_profile(self):
        with self.assertRaises(HTTPException) as error:
            update_ai_consent(
                AIConsentUpdate(ai_processing_consent=True),
                self.user,
                FakeProfileRepository(),
                SimpleNamespace(record=lambda *args: None),
            )
        self.assertEqual(error.exception.status_code, 404)

    def test_basic_user_update_cannot_accept_email_or_role(self):
        update = BasicUserUpdate(name="Updated Patient", tel="+34222222222")
        self.service.update_basic_user(self.user, update)

        self.assertEqual(self.user.name, "Updated Patient")
        self.assertEqual(self.user.tel, "+34222222222")
        self.assertNotIn("email", update.model_dump())
        self.assertNotIn("role", update.model_dump())

    def test_change_password_verifies_old_password_and_increments_session(self):
        self.service.change_password(
            self.user,
            ChangePasswordRequest(
                current_password="OldPassword123!",
                new_password="NewPassword123!",
            ),
        )

        self.assertTrue(verify_password("NewPassword123!", self.user.password_hash))
        self.assertEqual(self.user.session_version, 1)
        self.assertEqual(self.users.session.flush_count, 1)

    def test_change_password_rejects_wrong_current_password(self):
        with self.assertRaises(InvalidCurrentPasswordError):
            self.service.change_password(
                self.user,
                ChangePasswordRequest(
                    current_password="WrongPassword123!",
                    new_password="NewPassword123!",
                ),
            )
        self.assertEqual(self.user.session_version, 0)

    def test_patient_profile_endpoint_returns_only_owned_profile(self):
        result = get_patient_profile(self.user, self.profiles)
        self.assertIs(result, self.patient_profile)

    def test_patient_profile_endpoint_returns_404_when_missing(self):
        with self.assertRaises(HTTPException) as error:
            get_patient_profile(self.user, FakeProfileRepository())
        self.assertEqual(error.exception.status_code, 404)

    def test_patient_health_fields_require_ai_conversation(self):
        for data in (PatientProfileUpdate(blood_type="O+"), PatientProfileUpdate(height_cm=180), PatientProfileUpdate(weight_kg=75)):
            with self.assertRaises(HTTPException) as error:
                update_patient_profile(data, self.user, self.profiles)
            self.assertEqual(error.exception.status_code, 409)

    def test_patient_password_endpoint_returns_bad_request_for_wrong_password(self):
        with self.assertRaises(HTTPException) as error:
            change_patient_password(
                ChangePasswordRequest(
                    current_password="WrongPassword123!",
                    new_password="NewPassword123!",
                ),
                self.user,
                self.users,
                BackgroundTasks(),
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_patient_password_change_schedules_confirmation_and_limits_attempts(self):
        tasks = BackgroundTasks()
        data = ChangePasswordRequest(current_password="OldPassword123!", new_password="NewPassword123!")
        with (
            patch("app.api.profiles.patient_password_change_limiter", InMemoryRateLimiter(1, 900)),
            patch("app.api.profiles.send_password_changed_email") as send_email,
        ):
            change_patient_password(data, self.user, self.users, tasks)
            with self.assertRaises(HTTPException) as error:
                change_patient_password(data, self.user, self.users, tasks)
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(self.users.session.commit_count, 1)
        self.assertEqual(len(tasks.tasks), 1)
        self.assertIs(tasks.tasks[0].func, send_email)
        self.assertEqual(tasks.tasks[0].args, (self.user.email, self.user.name))

    def test_role_dependencies_reject_wrong_roles(self):
        professional = SimpleNamespace(role=UserRole.PROFESSIONAL)
        patient = SimpleNamespace(role=UserRole.PATIENT)
        with self.assertRaises(HTTPException) as patient_error:
            get_current_patient(professional)
        with self.assertRaises(HTTPException) as professional_error:
            get_current_professional(patient)
        self.assertEqual(patient_error.exception.status_code, 403)
        self.assertEqual(professional_error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
