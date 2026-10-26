import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService, InvalidAccessTokenError


class LogoutRepositoryTests(unittest.TestCase):
    def test_atomic_session_invalidation_persists_and_rejects_old_access(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        self.addCleanup(engine.dispose)
        User.__table__.create(engine)
        with Session(engine) as db:
            user = User(
                name="Synthetic test", dni="TEST-LOGOUT", username="logout_test",
                email="logout@example.invalid", password_hash="test-only-not-a-real-hash",
                tel="000000000", birth_date=date(2000, 1, 1), role=UserRole.PATIENT,
                is_active=True, session_version=0,
            )
            repository = UserRepository(db)
            repository.create(user)
            service = AuthService(repository)
            token = service.issue_access_token(user)
            service.logout(user)
            service.logout(user)
            db.commit()
            db.expire_all()
            self.assertEqual(repository.get_by_id(user.id).session_version, 2)
            with self.assertRaises(InvalidAccessTokenError):
                service.get_current_user(token)
            from app.main import app
            from app.api.deps import get_user_repository
            previous = app.dependency_overrides.copy()
            try:
                app.dependency_overrides[get_user_repository] = lambda: repository
                client = TestClient(app)
                fresh_token = service.issue_access_token(user)
                headers = {"Authorization": f"Bearer {fresh_token}"}
                self.assertEqual(client.get("/auth/me", headers=headers).status_code, 200)
                self.assertEqual(client.post("/auth/logout", headers=headers).status_code, 204)
                self.assertEqual(client.get("/auth/me", headers=headers).status_code, 401)
                client.close()
            finally:
                app.dependency_overrides.clear()
                app.dependency_overrides.update(previous)


if __name__ == "__main__":
    unittest.main()
