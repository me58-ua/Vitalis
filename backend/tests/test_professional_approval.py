import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models import ProfessionalApprovalStatus, UserRole
from app.services.professional_approval_service import (
    ProfessionalApprovalError,
    ProfessionalApprovalService,
)


class FakeSession:
    def flush(self):
        pass


class FakeProfessionals:
    def __init__(self, profile):
        self.profile = profile
        self.session = FakeSession()

    def get_profile_by_user_id(self, user_id):
        return self.profile if self.profile.user_id == user_id else None

    def list_pending_profiles(self):
        return [self.profile]


class FakeUsers:
    def __init__(self, user):
        self.user = user

    def get_by_id(self, user_id):
        return self.user if self.user.id == user_id else None


class ProfessionalApprovalTests(unittest.TestCase):
    def setUp(self):
        self.professional_id = uuid.uuid4()
        self.admin_id = uuid.uuid4()
        self.profile = SimpleNamespace(
            user_id=self.professional_id,
            approval_status=ProfessionalApprovalStatus.PENDING,
            rejection_reason=None,
            reviewed_at=None,
            reviewed_by=None,
        )
        self.user = SimpleNamespace(id=self.professional_id, role=UserRole.PROFESSIONAL, is_active=False)
        self.admin = SimpleNamespace(id=self.admin_id, role=UserRole.ADMIN)
        self.service = ProfessionalApprovalService(FakeProfessionals(self.profile), FakeUsers(self.user))

    def test_approval_activates_professional_and_records_reviewer(self):
        result = self.service.decide(
            self.professional_id, self.admin, ProfessionalApprovalStatus.APPROVED
        )
        self.assertIs(result, self.profile)
        self.assertEqual(self.profile.approval_status, ProfessionalApprovalStatus.APPROVED)
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.profile.reviewed_by, self.admin_id)
        self.assertIsInstance(self.profile.reviewed_at, datetime)

    def test_rejection_requires_reason_and_deactivates_professional(self):
        result = self.service.decide(
            self.professional_id,
            self.admin,
            ProfessionalApprovalStatus.REJECTED,
            "Falta documentación",
        )
        self.assertIs(result, self.profile)
        self.assertEqual(self.profile.rejection_reason, "Falta documentación")
        self.assertFalse(self.user.is_active)

    def test_rejection_without_reason_is_rejected(self):
        with self.assertRaises(ProfessionalApprovalError):
            self.service.decide(
                self.professional_id,
                self.admin,
                ProfessionalApprovalStatus.REJECTED,
            )


if __name__ == "__main__":
    unittest.main()
