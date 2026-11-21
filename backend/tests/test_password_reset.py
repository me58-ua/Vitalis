## no se persiste el token original, el token anterior queda invalidado, el token es de un solo uso, expira y aumenta la versión de sesión

import re
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import auth
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import hash_password_reset_token, verify_password
from app.services.password_reset_service import InvalidPasswordResetToken, PasswordResetService


class FakeSession:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def flush(self):
        pass


class FakeResetRepository:
    def __init__(self, user):
        self.user = user
        self.tokens = []
        self.session = FakeSession()

    def get_by_id(self, user_id):
        return self.user if user_id == self.user.id else None

    def get_by_email(self, email):
        return self.user if email == self.user.email else None

    def invalidate_password_reset_tokens(self, user_id):
        now = datetime.now(timezone.utc)
        for token in self.tokens:
            if token.user_id == user_id and token.used_at is None:
                token.used_at = now

    def create_password_reset_token(self, token):
        self.tokens.append(token)
        return token

    def get_active_password_reset_token(self, token_hash):
        return next(
            (
                token
                for token in self.tokens
                if token.token_hash == token_hash and token.used_at is None
            ),
            None,
        )


class PasswordResetServiceTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(
            id=uuid.uuid4(),
            email="patient@example.com",
            name="Patient",
            password_hash="old-hash",
            is_active=True,
            session_version=0,
        )
        self.repository = FakeResetRepository(self.user)
        self.service = PasswordResetService(self.repository)

    def test_only_token_hash_is_stored_and_previous_tokens_are_invalidated(self):
        first_token = self.service.issue_token(self.user)
        second_token = self.service.issue_token(self.user)

        self.assertNotEqual(first_token, self.repository.tokens[0].token_hash)
        self.assertEqual(hash_password_reset_token(second_token), self.repository.tokens[1].token_hash)
        self.assertIsNone(self.repository.get_active_password_reset_token(hash_password_reset_token(first_token)))

    def test_reset_is_one_time_and_invalidates_existing_session_version(self):
        token = self.service.issue_token(self.user)

        reset_user = self.service.reset_password(token, "NewStrongPass123!")

        self.assertIs(reset_user, self.user)
        self.assertTrue(verify_password("NewStrongPass123!", self.user.password_hash))
        self.assertEqual(self.user.session_version, 1)
        with self.assertRaises(InvalidPasswordResetToken):
            self.service.reset_password(token, "AnotherStrongPass123!")

    def test_expired_token_is_rejected(self):
        token = self.service.issue_token(self.user)
        self.repository.tokens[0].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        with self.assertRaises(InvalidPasswordResetToken):
            self.service.reset_password(token, "NewStrongPass123!")

    def test_recovery_emails_and_rate_limits(self):
        app = FastAPI()
        app.include_router(auth.router, prefix="/auth")
        app.dependency_overrides[auth.get_user_repository] = lambda: self.repository
        with (
            TestClient(app, client=("192.0.2.1", 5000)) as client,
            TestClient(app, client=("192.0.2.2", 5000)) as other_client,
            patch("app.services.password_reset_service.password_reset_rate_limiter", InMemoryRateLimiter(1, 900)),
            patch.object(auth, "password_reset_confirmation_limiter", InMemoryRateLimiter(2, 900)),
            patch("app.services.email_service._send_email", return_value=True) as send_email,
        ):
            forgot = "/auth/forgot-password"
            accepted = client.post(forgot, json={"email": self.user.email.upper()})
            self.assertEqual(accepted.status_code, 202)
            self.assertEqual(client.post(forgot, json={"email": "unknown@example.com"}).json(), accepted.json())
            self.assertEqual(other_client.post(forgot, json={"email": self.user.email}).json(), accepted.json())
            send_email.assert_called_once()
            email, subject, body_html = send_email.call_args.args
            self.assertEqual(email, self.user.email)
            self.assertIn("Restablece tu contraseña", subject)
            reset_link = re.search(r'/reset-password\?token=([\w-]+)"', body_html)
            self.assertIsNotNone(reset_link)
            token = reset_link.group(1)
            self.assertEqual(self.repository.session.commits, 1)

            reset = "/auth/reset-password"
            body = {"token": token, "password": "NewStrongPass123!"}
            self.assertEqual(client.post(reset, json={**body, "token": "invalid"}).status_code, 400)
            self.assertEqual(client.post(reset, json=body).status_code, 204)
            limited = client.post(reset, json=body)
            self.assertEqual(limited.status_code, 429)
            self.assertEqual(limited.headers["Retry-After"], "900")
            self.assertEqual(send_email.call_count, 2)
            email, subject, body_html = send_email.call_args.args
            self.assertEqual(email, self.user.email)
            self.assertIn("Contraseña actualizada", subject)
            self.assertNotIn(token, body_html)
            self.assertNotIn(body["password"], body_html)
            self.assertEqual(self.repository.session.commits, 2)


if __name__ == "__main__":
    unittest.main()
