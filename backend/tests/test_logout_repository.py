"""Login-session isolation tests using synthetic data in an in-memory DB."""
import unittest
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.auth import router
from app.api.deps import get_user_repository
from app.core.security import create_access_token, decode_access_token
from app.models import RefreshToken, User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService, InvalidAccessTokenError, InvalidRefreshTokenError


class LogoutRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        User.__table__.create(self.engine)
        RefreshToken.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.repository = UserRepository(self.db)
        self.user = self.make_user("first")
        self.other_user = self.make_user("second")
        self.service = AuthService(self.repository)
        app = FastAPI()
        app.include_router(router, prefix="/auth")
        app.dependency_overrides[get_user_repository] = lambda: self.repository
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def make_user(self, identifier):
        user = User(name="Synthetic test", dni=f"TEST-{identifier}", username=identifier,
                    email=f"{identifier}@example.invalid", password_hash="test-only",
                    tel="000000000", birth_date=date(2000, 1, 1), role=UserRole.PATIENT, is_active=True)
        return self.repository.create(user)

    def test_logout_only_revokes_this_login_not_other_logins_or_accounts(self):
        access, refresh = self.service.issue_tokens(self.user)
        second_access, second_refresh = self.service.issue_tokens(self.user)
        other_access, other_refresh = self.service.issue_tokens(self.other_user)
        headers = {"Authorization": f"Bearer {access}"}
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/auth/logout", headers=headers).status_code, 204)
        self.db.commit()
        self.db.expire_all()
        self.assertEqual(self.user.session_version, 0)
        self.assertEqual(self.client.get("/auth/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.post("/auth/refresh", json={"refresh_token": refresh}).status_code, 401)
        self.assertEqual(self.client.post("/auth/logout", headers=headers).status_code, 401)
        for token in (second_access, other_access):
            self.assertEqual(self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code, 200)
        for token in (second_refresh, other_refresh):
            self.assertEqual(self.client.post("/auth/refresh", json={"refresh_token": token}).status_code, 200)

    def test_refresh_rotates_secret_but_logout_revokes_the_same_session(self):
        access, refresh = self.service.issue_tokens(self.user)
        new_access, new_refresh = self.service.refresh_tokens(refresh)
        self.assertEqual(decode_access_token(access)["sid"], decode_access_token(new_access)["sid"])
        self.assertNotEqual(refresh, new_refresh)
        with self.assertRaises(InvalidRefreshTokenError):
            self.service.refresh_tokens(refresh)
        self.service.logout(self.user, access)
        for token in (access, new_access):
            with self.assertRaises(InvalidAccessTokenError):
                self.service.get_current_user(token)
        with self.assertRaises(InvalidRefreshTokenError):
            self.service.refresh_tokens(new_refresh)

    def test_account_wide_revocation_still_works_for_password_reset(self):
        access, refresh = self.service.issue_tokens(self.user)
        other_access, _ = self.service.issue_tokens(self.user)
        self.repository.invalidate_sessions(self.user.id)
        for token in (access, other_access):
            with self.assertRaises(InvalidAccessTokenError):
                self.service.get_current_user(token)
        with self.assertRaises(InvalidRefreshTokenError):
            self.service.refresh_tokens(refresh)

    def test_legacy_access_requires_refresh_to_bind_to_a_session(self):
        legacy_access = create_access_token(str(self.user.id), self.user.role.value, self.user.session_version)
        with self.assertRaises(InvalidAccessTokenError):
            self.service.get_current_user(legacy_access)
        self.assertEqual(self.client.post("/auth/logout").status_code, 401)


if __name__ == "__main__":
    unittest.main()
