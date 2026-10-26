import unittest
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.api.auth import login, me, register
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import UserRole
from app.schemas.auth import UserRegisterRequest
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UsernameAlreadyRegisteredError,
)
from app.services.email_service import send_welcome_email


class FakeUserRepository:
    def __init__(self):
        self.users = {}
        self.refresh_tokens = {}
        self.session = SimpleNamespace(flush=lambda: None)

    def get_by_email(self, email):
        return self.users.get(email)

    def get_by_username(self, username):
        return next((user for user in self.users.values() if user.username == username), None)

    def get_by_id(self, user_id):
        return next((user for user in self.users.values() if user.id == user_id), None)

    def create(self, user):
        user.id = uuid.uuid4()
        user.created_at = datetime.now(timezone.utc)
        user.updated_at = user.created_at
        if user.is_active is None:
            user.is_active = True
        if user.session_version is None:
            user.session_version = 0
        self.users[user.email] = user
        return user

    def create_refresh_token(self, refresh_token):
        self.refresh_tokens[refresh_token.token_hash] = refresh_token
        return refresh_token

    def get_active_refresh_token(self, token_hash):
        refresh_token = self.refresh_tokens.get(token_hash)
        if refresh_token is None or refresh_token.revoked_at is not None:
            return None
        return refresh_token

    def invalidate_sessions(self, user_id):
        self.get_by_id(user_id).session_version += 1


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeUserRepository()
        self.service = AuthService(self.repository)
        self.data = UserRegisterRequest(
            role=UserRole.PATIENT,
            name="New Patient",
            dni="X1234567L",
            username="new_patient",
            email="new.patient@example.com",
            password="StrongPass123!",
            tel="+34123456789",
            birth_date=date(1995, 6, 15),
            gender=None,
            terms_accepted=True,
        )

    def test_password_is_hashed_and_verifies(self):
        password_hash = hash_password("StrongPass123!")
        self.assertNotEqual(password_hash, "StrongPass123!")
        self.assertTrue(verify_password("StrongPass123!", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_registers_patient_without_storing_plaintext_password(self):
        user = self.service.register_patient(self.data)
        self.assertEqual(user.role, UserRole.PATIENT)
        self.assertNotEqual(user.password_hash, self.data.password)
        self.assertEqual(user.email, self.data.email)
        self.assertEqual(user.dni, self.data.dni)
        self.assertIsNotNone(user.patient_profile)
        self.assertIsNone(user.patient_profile.address)

    def test_registers_professional_as_inactive_with_professional_profile(self):
        data = UserRegisterRequest(
            role=UserRole.PROFESSIONAL,
            name="New Professional",
            dni="Y1234567X",
            username="new_professional",
            email="new.professional@example.com",
            password="StrongPass123!",
            tel="+34123456789",
            birth_date=date(1985, 6, 15),
            terms_accepted=True,
            specialty="Cardiology",
            bio="Experienced cardiologist",
            practice_address="Madrid",
            practice_phone="+34910000000",
            is_accepting_new_patients=True,
            default_consultation_duration_minutes=30,
            telehealth_enabled=True,
            license_number="COL-12345",
        )
        user = self.service.register_user(data)
        self.assertEqual(user.role, UserRole.PROFESSIONAL)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.professional_profile)
        self.assertEqual(user.professional_profile.specialty, "Cardiology")

    def test_registration_requires_terms_acceptance(self):
        with self.assertRaises(ValueError):
            UserRegisterRequest(**{**self.data.model_dump(), "terms_accepted": False})

    def test_duplicate_email_is_rejected(self):
        self.service.register_patient(self.data)
        with self.assertRaises(EmailAlreadyRegisteredError):
            self.service.register_patient(self.data)

    def test_duplicate_username_is_rejected(self):
        self.service.register_patient(self.data)
        duplicate = self.data.model_copy(update={"email": "other@example.com"})
        with self.assertRaises(UsernameAlreadyRegisteredError):
            self.service.register_patient(duplicate)

    def test_login_returns_user_and_token_contains_subject_and_role(self):
        user = self.service.register_patient(self.data)
        authenticated = self.service.authenticate(self.data.email, self.data.password)
        token = self.service.issue_access_token(authenticated)
        payload = decode_access_token(token)
        self.assertEqual(authenticated.id, user.id)
        self.assertEqual(payload["sub"], str(user.id))
        self.assertEqual(payload["role"], "patient")

    def test_login_accepts_username(self):
        user = self.service.register_patient(self.data)
        authenticated = self.service.authenticate(self.data.username, self.data.password)
        self.assertEqual(authenticated.id, user.id)

    def test_wrong_password_is_rejected(self):
        self.service.register_patient(self.data)
        with self.assertRaises(InvalidCredentialsError):
            self.service.authenticate(self.data.email, "wrong-password")

    def test_register_endpoint_returns_created_patient(self):
        user = register(self.data, self.repository)
        self.assertEqual(user.email, self.data.email)
        self.assertEqual(user.role, UserRole.PATIENT)

    def test_register_endpoint_enqueues_welcome_email(self):
        tasks = []

        class FakeBackgroundTasks:
            def add_task(self, func, *args, **kwargs):
                tasks.append((func, args, kwargs))

        user = register(self.data, self.repository, background_tasks=FakeBackgroundTasks())

        self.assertEqual(user.email, self.data.email)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0][0], send_welcome_email)
        self.assertEqual(tasks[0][1], (self.data.email, self.data.name))

    def test_register_endpoint_rejects_duplicate_email(self):
        register(self.data, self.repository)
        with self.assertRaises(HTTPException) as error:
            register(self.data, self.repository)
        self.assertEqual(error.exception.status_code, 409)

    def test_login_endpoint_returns_bearer_token(self):
        user = self.service.register_patient(self.data)
        form_data = OAuth2PasswordRequestForm(
            username=self.data.email,
            password=self.data.password,
        )
        response = login(form_data, self.repository)
        payload = decode_access_token(response.access_token)
        self.assertEqual(response.token_type, "bearer")
        self.assertEqual(payload["sub"], str(user.id))
        self.assertTrue(response.refresh_token)

    def test_refresh_token_rotates_and_revokes_previous_token(self):
        user = self.service.register_patient(self.data)
        first_refresh_token = self.service.issue_refresh_token(user)

        access_token, second_refresh_token = self.service.refresh_tokens(first_refresh_token)

        self.assertNotEqual(first_refresh_token, second_refresh_token)
        self.assertEqual(decode_access_token(access_token)["sub"], str(user.id))
        self.assertIsNone(self.repository.get_active_refresh_token(hash_refresh_token(first_refresh_token)))

    def test_me_endpoint_returns_current_user(self):
        user = self.service.register_patient(self.data)
        self.assertIs(me(user), user)

    def test_logout_invalidates_access_and_refresh_and_allows_new_login(self):
        from app.services.auth_service import InvalidAccessTokenError, InvalidRefreshTokenError
        from app.api.auth import logout
        user = self.service.register_patient(self.data)
        access = self.service.issue_access_token(user)
        refresh = self.service.issue_refresh_token(user)
        self.assertIs(self.service.get_current_user(access), user)
        logout(user, self.repository)
        with self.assertRaises(InvalidAccessTokenError):
            self.service.get_current_user(access)
        with self.assertRaises(InvalidRefreshTokenError):
            self.service.refresh_tokens(refresh)
        self.assertIs(self.service.get_current_user(self.service.issue_access_token(user)), user)
        self.assertTrue(self.service.refresh_tokens(self.service.issue_refresh_token(user)))


if __name__ == "__main__":
    unittest.main()
