import unittest
import uuid

from app.models import AuditAction, UserRole
from app.services.audit_service import AuditService


class FakeAuditRepository:
    def __init__(self):
        self.logs = []

    def create(self, log):
        self.logs.append(log)
        return log


class AuditServiceTests(unittest.TestCase):
    def test_record_persists_the_complete_audit_context(self):
        repository = FakeAuditRepository()
        actor_id = uuid.uuid4()
        patient_id = uuid.uuid4()
        entity_id = uuid.uuid4()

        result = AuditService(repository).record(
            actor_id,
            UserRole.PROFESSIONAL,
            AuditAction.READ,
            "patient_profile",
            entity_id,
            patient_id,
        )

        self.assertIs(result, repository.logs[0])
        self.assertEqual(result.actor_id, actor_id)
        self.assertEqual(result.actor_role, UserRole.PROFESSIONAL)
        self.assertEqual(result.accion, AuditAction.READ)
        self.assertEqual(result.entidad, "patient_profile")
        self.assertEqual(result.entidad_id, entity_id)
        self.assertEqual(result.patient_id, patient_id)

    def test_without_repository_no_audit_row_is_created(self):
        self.assertIsNone(
            AuditService(None).record(
                uuid.uuid4(), UserRole.PATIENT, AuditAction.UPDATE, "patient_profile"
            )
        )


if __name__ == "__main__":
    unittest.main()