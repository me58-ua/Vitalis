## no se persiste el token original, el token anterior queda invalidado, el token es de un solo uso, expira y aumenta la versión de sesión

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.security import hash_password_reset_token, verify_password
from app.services.password_reset_service import InvalidPasswordResetToken, PasswordResetService


class FakeSession:
    def flush(self):
        pass


class FakeResetRepository:
    def __init__(self, user):
        self.user = user
        self.tokens = []
        self.session = FakeSession()

    def get_by_id(self, user_id):
        return self.user if user_id == self.user.id else None

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


if __name__ == "__main__":
    unittest.main()
