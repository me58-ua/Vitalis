import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.professional_management import router
from app.api.deps import get_current_user, get_audit_repository, get_profile_repository
from app.database import get_db
from app.models import ProfessionalApprovalStatus, UserRole, ProfessionalTimeBlock
from app.schemas.profiles import ProfessionalProfileUpdate, ProfessionalProfileResponse
from app.schemas.professional_management import ProfileChangeDecision, TimeBlockCreate
from app.services.profile_change_service import ProfileChangeService, ProfileChangeConflict, ProfileChangeValidation
from app.services.profile_service import ProfileNotFoundError
from app.services.time_block_service import TimeBlockService
from app.services.appointment_service import AppointmentConflictError, AppointmentNotFoundError


class ProfileChangeTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL, is_active=True)
        self.admin = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
        self.profile = SimpleNamespace(id=uuid4(), user_id=self.user.id, specialty="Medicina general", license_number="COL-1",
                                       bio=None, approval_status=ProfessionalApprovalStatus.APPROVED)
        self.repo = Mock()
        self.repo.lock_professional.return_value = self.profile
        self.audits = Mock()
        self.service = ProfileChangeService(self.repo, self.audits)

    def submit(self, **values):
        return self.service.submit(self.user, ProfessionalProfileUpdate(**values))

    def decision(self, reason=None):
        return ProfileChangeDecision(request_id=self.profile.change_request_id, reason=reason)

    def test_submission_keeps_live_profile_and_access_and_audits(self):
        self.submit(specialty="Cardiología", bio="Consulta preventiva")
        self.assertEqual(self.profile.specialty, "Medicina general")
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.profile.approval_status, ProfessionalApprovalStatus.APPROVED)
        self.assertEqual(self.profile.pending_changes, {"specialty": "Cardiología", "bio": "Consulta preventiva"})
        self.assertEqual(self.profile.change_status, "pending")
        self.audits.create.assert_called_once()

    def test_languages_and_experience_are_published_only_after_approval(self):
        self.profile.languages = ['Español']
        self.profile.years_experience = None
        self.submit(languages=['Español', ' English '], years_experience=12)
        self.assertEqual(self.profile.languages, ['Español'])
        self.assertIsNone(self.profile.years_experience)
        self.assertEqual(self.profile.pending_changes['languages'], ['Español', 'English'])
        self.service.decide(self.user.id, self.admin, self.decision(), True)
        self.assertEqual(self.profile.languages, ['Español', 'English'])
        self.assertEqual(self.profile.years_experience, 12)
        self.submit(languages=[], years_experience=None)
        self.service.decide(self.user.id, self.admin, self.decision(), True)
        self.assertEqual(self.profile.languages, [])
        self.assertIsNone(self.profile.years_experience)

    def test_languages_and_experience_validation(self):
        for payload in ({'languages': None}, {'languages': [' ']}, {'languages': ['Español', 'español']},
                        {'languages': ['a' * 61]}, {'languages': [str(i) for i in range(21)]},
                        {'years_experience': -1}, {'years_experience': 81}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ProfessionalProfileUpdate(**payload)

    def test_approval_applies_changes_and_records_admin_without_reactivating(self):
        self.submit(specialty="Cardiología")
        self.user.is_active = False
        self.service.decide(self.user.id, self.admin, self.decision(), True)
        self.assertEqual(self.profile.specialty, "Cardiología")
        self.assertIsNone(self.profile.pending_changes)
        self.assertEqual(self.profile.change_reviewed_by, self.admin.id)
        self.assertEqual(self.profile.change_status, "approved")
        self.assertFalse(self.user.is_active)

    def test_rejection_retains_live_data_and_allows_resubmission(self):
        self.submit(specialty="Cardiología")
        self.service.decide(self.user.id, self.admin, self.decision("Falta acreditación"), False)
        self.assertEqual(self.profile.specialty, "Medicina general")
        self.assertEqual(self.profile.change_status, "rejected")
        self.assertEqual(self.profile.change_rejection_reason, "Falta acreditación")
        self.submit(specialty="Neurología")
        self.assertEqual(self.profile.change_status, "pending")
        self.assertIsNone(self.profile.change_rejection_reason)

    def test_replacement_and_repeated_decisions_are_rejected(self):
        self.submit(specialty="Cardiología")
        old = self.decision()
        self.submit(bio="Nueva presentación")
        self.assertEqual(self.profile.pending_changes, {"bio": "Nueva presentación"})
        with self.assertRaises(ProfileChangeConflict):
            self.service.decide(self.user.id, self.admin, old, True)
        current = self.decision()
        self.service.decide(self.user.id, self.admin, current, True)
        with self.assertRaises(ProfileChangeConflict):
            self.service.decide(self.user.id, self.admin, current, True)

    def test_rejection_needs_nonblank_reason(self):
        self.submit(specialty="Cardiología")
        with self.assertRaises(ProfileChangeValidation):
            self.service.decide(self.user.id, self.admin, self.decision("   "), False)
        self.assertEqual(self.profile.change_status, "pending")

    def test_required_fields_and_untrusted_keys_are_validated(self):
        for payload in ({"specialty": None}, {"license_number": "  "}, {"telehealth_enabled": None}, {"approval_status": "approved"}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ProfessionalProfileUpdate(**payload)

    def test_review_response_keeps_only_requested_fields_including_explicit_null(self):
        response = ProfessionalProfileResponse(
            id=uuid4(), user_id=self.user.id, specialty='Medicina general', license_number='COL-1',
            approval_status=ProfessionalApprovalStatus.APPROVED, rejection_reason=None, reviewed_at=None, reviewed_by=None,
            pending_changes={'specialty': 'Cardiología', 'bio': None},
        )
        self.assertEqual(response.model_dump(mode='json')['pending_changes'], {'specialty': 'Cardiología', 'bio': None})

    def test_empty_unchanged_unapproved_or_missing_profile(self):
        for payload in ({}, {"specialty": "Medicina general"}):
            with self.assertRaises(ProfileChangeValidation): self.submit(**payload)
        self.profile.approval_status = ProfessionalApprovalStatus.PENDING
        with self.assertRaises(ProfileChangeValidation): self.submit(bio="Texto")
        self.repo.lock_professional.return_value = None
        with self.assertRaises(ProfileNotFoundError): self.submit(bio="Texto")

    def test_duplicate_license_on_approval_rolls_back(self):
        self.submit(license_number="COL-DUP")
        self.repo.session.flush.side_effect = IntegrityError("insert", {}, Exception("duplicate"))
        with self.assertRaises(ProfileChangeConflict):
            self.service.decide(self.user.id, self.admin, self.decision(), True)
        self.repo.session.rollback.assert_called_once()


class TimeBlockTests(unittest.TestCase):
    def test_interval_requires_timezone_and_positive_duration(self):
        for start, end in (("2030-01-01T10:00:00", "2030-01-01T11:00:00"),
                           ("2030-01-01T11:00:00Z", "2030-01-01T10:00:00Z"),
                           ("2030-01-01T10:00:00Z", "2030-01-01T10:00:00Z")):
            with self.assertRaises(ValidationError): TimeBlockCreate(start_time=start, end_time=end)

    def test_create_conflict_is_409_domain_error_and_rollback(self):
        repo = Mock()
        repo.create.side_effect = IntegrityError("insert", {}, Exception("conflict"))
        start = datetime.now(timezone.utc)
        with self.assertRaises(AppointmentConflictError):
            TimeBlockService(repo).create(SimpleNamespace(id=uuid4()), TimeBlockCreate(start_time=start, end_time=start + timedelta(hours=1)))
        repo.session.rollback.assert_called_once()

    def test_delete_uses_authenticated_owner_and_audits(self):
        repo, audits = Mock(), Mock()
        user = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL)
        block_id = uuid4()
        repo.get_owned.return_value = None
        with self.assertRaises(AppointmentNotFoundError): TimeBlockService(repo).delete(user, block_id)
        repo.delete.assert_not_called()
        repo.get_owned.return_value = ProfessionalTimeBlock(id=block_id, professional_id=user.id)
        TimeBlockService(repo, audits).delete(user, block_id)
        repo.get_owned.assert_called_with(user.id, block_id)
        audits.create.assert_called_once()


class ProfessionalManagementApiTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.user = SimpleNamespace(id=uuid4(), role=UserRole.PATIENT, is_active=True)
        self.db = Mock()
        self.profiles = Mock()
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_audit_repository] = lambda: None
        self.app.dependency_overrides[get_profile_repository] = lambda: self.profiles
        self.client = TestClient(self.app)

    def test_patients_and_professionals_cannot_review_changes(self):
        for role in (UserRole.PATIENT, UserRole.PROFESSIONAL):
            self.user.role = role
            self.assertEqual(self.client.get('/admin/professionals/profile-changes').status_code, 403)
            response = self.client.post(f'/admin/professionals/{uuid4()}/profile-change/approve', json={"request_id": str(uuid4())})
            self.assertEqual(response.status_code, 403)
        self.profiles.lock_professional.assert_not_called()

    def test_only_professionals_manage_blocks_and_range_validation(self):
        self.assertEqual(self.client.get('/professionals/me/time-blocks?from_date=2030-01-01&to_date=2030-01-07').status_code, 403)
        self.user.role = UserRole.PROFESSIONAL
        for query in ('from_date=2030-01-07&to_date=2030-01-01', 'from_date=2030-01-01&to_date=2032-01-01'):
            self.assertEqual(self.client.get('/professionals/me/time-blocks?' + query).status_code, 422)
        self.db.scalars.assert_not_called()


if __name__ == '__main__':
    unittest.main()
