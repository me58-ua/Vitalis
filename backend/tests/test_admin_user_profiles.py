"""Synthetic, isolated SQLite tests: no configured database or patient data is used."""
import unittest
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_audit_repository, get_current_admin, get_user_repository
from app.api.users import router
from app.models import PatientProfile, ProfessionalApprovalStatus, ProfessionalProfile, User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.users import AdminUserCreate, AdminUserUpdate
from app.services.admin_user_service import AdminUserConflictError, AdminUserService, AdminUserValidationError


class AdminProfileTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for table in (User.__table__, PatientProfile.__table__, ProfessionalProfile.__table__):
            table.create(self.engine)
        self.db = Session(self.engine)
        self.repo = UserRepository(self.db)
        self.service = AdminUserService(self.repo)
        self.account = dict(name="Synthetic account", dni="TEST-12345", username="synthetic", email="synthetic@example.invalid",
                            password="SyntheticPass123!", tel="000000000", birth_date="1990-01-01", role="patient")
        app = FastAPI()
        app.include_router(router)
        admin = User(role=UserRole.ADMIN)
        app.dependency_overrides[get_current_admin] = lambda: admin
        app.dependency_overrides[get_user_repository] = lambda: self.repo
        app.dependency_overrides[get_audit_repository] = lambda: None
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_patient_account_and_profile_persist_together_without_consent(self):
        response = self.client.post("/admin/users", json={**self.account, "patient_profile": {
            "address": "Synthetic address", "height_cm": 175, "weight_kg": 70, "timezone": "Atlantic/Canary", "blood_type": "O+"}})
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["patient_profile"]["height_cm"], 175)
        self.assertEqual(body["patient_profile"]["timezone"], "Atlantic/Canary")
        stored = self.db.scalar(select(User).where(User.username == "synthetic"))
        self.assertEqual(stored.patient_profile.birth_date, date(1990, 1, 1))
        self.assertFalse(stored.patient_profile.ai_processing_consent)
        self.assertFalse(stored.patient_profile.share_health_data)
        self.assertNotIn("password", body)
        self.assertNotIn("password_hash", body)
        detail = self.client.get(f'/admin/users/{body["id"]}')
        self.assertEqual(detail.json()["patient_profile"]["address"], "Synthetic address")
        listing = self.client.get("/admin/users").json()
        self.assertNotIn("patient_profile", listing["users"][0])

    def test_professional_profile_required_and_starts_pending(self):
        missing = self.client.post("/admin/users", json={**self.account, "role": "professional"})
        self.assertEqual(missing.status_code, 422)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(User)), 0)
        response = self.client.post("/admin/users", json={**self.account, "role": "professional", "professional_profile": {
            "specialty": "Synthetic specialty", "license_number": "TEST-LICENSE", "telehealth_enabled": False}})
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertFalse(body["is_active"])
        self.assertEqual(body["professional_profile"]["approval_status"], "pending")
        self.assertFalse(body["professional_profile"]["telehealth_enabled"])
        activation = self.client.patch(f'/admin/users/{body["id"]}', json={"is_active": True})
        self.assertEqual(activation.status_code, 422)
        self.assertEqual(activation.json()["detail"], "PROFESSIONAL_APPROVAL_REQUIRED")

    def test_role_change_provisions_profile_and_preserves_old_profile(self):
        user = self.service.create(AdminUserCreate(**self.account))
        patient_id = user.patient_profile.id
        with self.assertRaises(AdminUserValidationError):
            self.service.update(user, AdminUserUpdate(role="professional"))
        self.assertEqual(user.role, UserRole.PATIENT)
        self.service.update(user, AdminUserUpdate(role="professional", professional_profile={
            "specialty": "Synthetic", "license_number": "TEST-CHANGE"}))
        self.assertEqual(user.professional_profile.approval_status, ProfessionalApprovalStatus.PENDING)
        self.assertFalse(user.is_active)
        self.assertEqual(user.patient_profile.id, patient_id)
        self.service.update(user, AdminUserUpdate(role="patient", birth_date=date(1991, 2, 3)))
        self.assertEqual(user.patient_profile.birth_date, date(1991, 2, 3))
        self.assertIsNotNone(user.professional_profile)

    def test_profile_conflict_rolls_back_the_entire_account_creation(self):
        first = AdminUserCreate(**{**self.account, "role": "professional", "professional_profile": {
            "specialty": "Synthetic", "license_number": "TEST-UNIQUE"}})
        self.service.create(first)
        self.db.commit()
        second = first.model_copy(update={"dni": "TEST-67890", "username": "second", "email": "second@example.invalid"})
        with self.assertRaises(AdminUserConflictError):
            self.service.create(second)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(User)), 1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ProfessionalProfile)), 1)

    def test_invalid_profile_and_required_nulls_return_422(self):
        for profile in ({"height_cm": 99}, {"weight_kg": 401}, {"timezone": "invalid/timezone"}):
            response = self.client.post("/admin/users", json={**self.account, "patient_profile": profile})
            self.assertEqual(response.status_code, 422)
        for field in ("name", "role", "email", "birth_date", "is_active"):
            response = self.client.patch("/admin/users/00000000-0000-4000-8000-000000000001", json={field: None})
            self.assertEqual(response.status_code, 422)

    def test_partial_profile_edit_preserves_omitted_fields_and_consent(self):
        user = self.service.create(AdminUserCreate(**self.account, patient_profile={"address": "Synthetic", "height_cm": 175}))
        user.patient_profile.ai_processing_consent = True
        self.service.update(user, AdminUserUpdate(patient_profile={"weight_kg": 80}))
        self.assertEqual(user.patient_profile.address, "Synthetic")
        self.assertEqual(user.patient_profile.height_cm, 175)
        self.assertTrue(user.patient_profile.ai_processing_consent)
        self.assertEqual(user.patient_profile.weight_kg, 80)

    def test_repairing_legacy_professional_creates_profile_and_requires_approval(self):
        user = self.service.create(AdminUserCreate(**self.account))
        user.role = UserRole.PROFESSIONAL
        user.is_active = True
        self.db.flush()
        self.service.update(user, AdminUserUpdate(professional_profile={
            "specialty": "Synthetic", "license_number": "TEST-LEGACY"}))
        self.assertIsNotNone(user.professional_profile)
        self.assertEqual(user.professional_profile.approval_status, ProfessionalApprovalStatus.PENDING)
        self.assertFalse(user.is_active)

    def test_authentication_and_admin_authorization_are_not_bypassed(self):
        from app.api.deps import get_current_user
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            self.assertEqual(client.get("/admin/users").status_code, 401)
            app.dependency_overrides[get_current_user] = lambda: User(role=UserRole.PATIENT)
            self.assertEqual(client.get("/admin/users").status_code, 403)


if __name__ == "__main__":
    unittest.main()
