import unittest
import uuid
from datetime import date
from types import SimpleNamespace

from app.models import (
    AuditAction,
    FamilyHistoryEntry,
    FamilyRelationship,
    HeredataryConditions,
    UserRole,
)
from app.services.family_history_service import (
    FamilyHistoryNotFoundError,
    FamilyHistoryService,
)


class FakeSession:
    def __init__(self):
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1


class FakeFamilyHistoryRepository:
    def __init__(self):
        self.rows = []

    def create(self, entry):
        entry.id = len(self.rows) + 1
        self.rows.append(entry)
        return entry

    def list_for_patient(self, patient_id):
        return [row for row in self.rows if row.patient_id == patient_id]

    def get_for_patient(self, patient_id, entry_id):
        return next(
            (
                row
                for row in self.rows
                if row.patient_id == patient_id and row.id == entry_id
            ),
            None,
        )

    def delete(self, entry):
        self.rows.remove(entry)


class FakeProfiles:
    def __init__(self, profile):
        self.profile = profile
        self.session = FakeSession()

    def get_patient(self, user_id):
        return self.profile if self.profile.user_id == user_id else None


class FakeAudits:
    def __init__(self):
        self.logs = []

    def create(self, log):
        self.logs.append(log)
        return log


class FakeRiskService:
    def __init__(self):
        self.calls = []

    def evaluate_and_record(self, patient_id, trigger):
        self.calls.append((patient_id, trigger))


class FamilyHistoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.user_id = uuid.uuid4()
        self.patient_id = uuid.uuid4()
        self.user = SimpleNamespace(id=self.user_id, role=UserRole.PATIENT)
        self.profile = SimpleNamespace(
            id=self.patient_id,
            user_id=self.user_id,
            family_history_reviewed=False,
        )
        self.repository = FakeFamilyHistoryRepository()
        self.profiles = FakeProfiles(self.profile)
        self.audits = FakeAudits()
        self.risk = FakeRiskService()
        self.service = FamilyHistoryService(
            self.repository, self.profiles, self.audits, self.risk
        )

    def test_create_marks_history_reviewed_and_triggers_family_risk(self):
        entry = self.service.create_from_onboarding(
            self.user,
            FamilyRelationship.MOTHER,
            HeredataryConditions.DIABETES,
            "Type 2",
            54,
            date(2026, 1, 2),
        )

        self.assertEqual(entry.patient_id, self.patient_id)
        self.assertTrue(self.profile.family_history_reviewed)
        self.assertEqual(self.risk.calls, [(self.patient_id, "family_change")])
        self.assertEqual(self.audits.logs[0].accion, AuditAction.CREATE)
        self.assertEqual(self.audits.logs[0].entidad, "family_history_entry")

    def test_declare_none_marks_history_reviewed_and_triggers_family_risk(self):
        self.service.declare_none_from_onboarding(self.user)

        self.assertTrue(self.profile.family_history_reviewed)
        self.assertEqual(self.risk.calls, [(self.patient_id, "family_change")])
        self.assertEqual(self.repository.rows, [])

    def test_delete_removes_owned_entry_without_unreviewing_history(self):
        entry = self.service.create_from_onboarding(
            self.user,
            FamilyRelationship.FATHER,
            HeredataryConditions.CANCER,
            None,
            None,
        )
        self.risk.calls.clear()

        self.service.delete_for_patient(self.user, entry.id)

        self.assertEqual(self.repository.rows, [])
        self.assertTrue(self.profile.family_history_reviewed)
        self.assertEqual(self.risk.calls, [(self.patient_id, "family_change")])
        self.assertEqual(self.audits.logs[-1].accion, AuditAction.DELETE)

    def test_invalid_age_and_detail_are_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_from_onboarding(
                self.user,
                FamilyRelationship.OTHER,
                HeredataryConditions.OTHER,
                "x" * 151,
                20,
            )
        with self.assertRaises(ValueError):
            self.service.create_from_onboarding(
                self.user,
                FamilyRelationship.OTHER,
                HeredataryConditions.OTHER,
                None,
                121,
            )

    def test_missing_entry_is_not_found(self):
        with self.assertRaises(FamilyHistoryNotFoundError):
            self.service.delete_for_patient(self.user, 99)

    def test_listing_is_limited_to_the_owned_patient_profile(self):
        self.service.create_from_onboarding(
            self.user,
            FamilyRelationship.SIBLING,
            HeredataryConditions.CARDIOVASCULAR,
            None,
            60,
        )
        another_user = SimpleNamespace(id=uuid.uuid4(), role=UserRole.PATIENT)

        with self.assertRaises(FamilyHistoryNotFoundError):
            self.service.list_for_patient(another_user)

        self.assertEqual(len(self.service.list_for_patient(self.user)), 1)


if __name__ == "__main__":
    unittest.main()
