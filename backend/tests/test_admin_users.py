import unittest
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from app.api.users import list_users, parse_role
from app.models import User, UserRole
from app.schemas.users import AdminUserCreate, AdminUserUpdate
from app.services.admin_user_service import AdminUserConflictError, AdminUserService
from app.core.security import verify_password


class FakeUserRepository:
    def __init__(self):
        self.users = []
        self.session = SimpleNamespace(flush=lambda: None)

    def create(self, user):
        user.id = user.id or uuid.uuid4()
        user.created_at = user.created_at or datetime.now(timezone.utc)
        user.updated_at = user.updated_at or user.created_at
        self.users.append(user)
        return user

    def update(self, user, values):
        for field, value in values.items():
            setattr(user, field, value)
        self.session.flush()
        return user

    def get_by_id(self, user_id):
        return next((user for user in self.users if user.id == user_id), None)

    def list(self, role, search, offset, limit):
        records = self.users
        if role is not None:
            records = [user for user in records if user.role == role]
        if search:
            value = search.lower()
            records = [
                user
                for user in records
                if value in user.name.lower()
                or value in user.email.lower()
                or value in user.username.lower()
            ]
        return records[offset : offset + limit], len(records)


class AdminUserTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeUserRepository()
        self.data = AdminUserCreate(
            name="Admin Created",
            dni="X1234567L",
            username="admin_created",
            email="admin.created@example.com",
            password="StrongPass123!",
            tel="+34123456789",
            birth_date=date(1990, 1, 1),
            role=UserRole.PATIENT,
        )

    def test_create_hashes_password_and_persists_dni(self):
        user = AdminUserService(self.repository).create(self.data)

        self.assertEqual(user.dni, "X1234567L")
        self.assertNotEqual(user.password_hash, self.data.password)
        self.assertTrue(verify_password(self.data.password, user.password_hash))
        self.assertEqual(user.role, UserRole.PATIENT)

    def test_update_is_partial_and_hashes_new_password(self):
        user = AdminUserService(self.repository).create(self.data)
        updated = AdminUserService(self.repository).update(
            user,
            AdminUserUpdate(name="Updated Name", password="NewStrongPass123!"),
        )

        self.assertEqual(updated.name, "Updated Name")
        self.assertTrue(verify_password("NewStrongPass123!", updated.password_hash))
        self.assertEqual(updated.email, self.data.email)
        self.assertEqual(updated.dni, self.data.dni)

    def test_parse_role_accepts_uppercase_and_rejects_unknown_values(self):
        self.assertEqual(parse_role("PROFESSIONAL"), UserRole.PROFESSIONAL)
        with self.assertRaises(HTTPException) as error:
            parse_role("nurse")
        self.assertEqual(error.exception.status_code, 422)

    def test_list_endpoint_passes_filter_and_pagination_to_repository(self):
        admin = SimpleNamespace(role=UserRole.ADMIN)
        captured = {}

        class ListingRepository:
            def list(self, **kwargs):
                captured.update(kwargs)
                return [], 27

        response = list_users(
            admin,
            ListingRepository(),
            role="PATIENT",
            search="ana",
            page=3,
            page_size=10,
        )

        self.assertEqual(response.total, 27)
        self.assertEqual(response.page, 3)
        self.assertEqual(response.page_size, 10)
        self.assertEqual(captured["role"], UserRole.PATIENT)
        self.assertEqual(captured["search"], "ana")
        self.assertEqual(captured["offset"], 20)
        self.assertEqual(captured["limit"], 10)


if __name__ == "__main__":
    unittest.main()
