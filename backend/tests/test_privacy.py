import tempfile
import unittest
import uuid
from types import SimpleNamespace

from app.models import UserRole
from app.services.file_storage import LocalFileStorage
from app.services.privacy_service import PrivacyService


class FakePrivacyRepository:
    def __init__(self, document_keys=None):
        self.document_keys = document_keys or []
        self.erased_patient_id = None
        self.revoked_user_id = None

    def erase_patient_health(self, patient_id):
        self.erased_patient_id = patient_id
        return self.document_keys

    def anonymize_patient_profile(self, profile):
        profile.address = None
        profile.blood_type = None
        profile.share_health_data = False

    def anonymize_professional_profile(self, profile):
        profile.specialty = "Cuenta eliminada"
        profile.license_number = f"deleted-{profile.user_id.hex[:12]}"
        profile.is_accepting_new_patients = False
        profile.telehealth_enabled = False

    def revoke_user_sessions(self, user_id):
        self.revoked_user_id = user_id

    def anonymize_user(self, user):
        user.name = "Cuenta eliminada"
        user.is_active = False
        user.session_version += 1


class FakeProfiles:
    def __init__(self, patient=None, professional=None):
        self.patient = patient
        self.professional = professional

    def get_patient(self, user_id):
        return self.patient if self.patient and self.patient.user_id == user_id else None

    def get_professional(self, user_id):
        return self.professional if self.professional and self.professional.user_id == user_id else None


class FakeAuditRepository:
    def __init__(self):
        self.logs = []

    def create(self, log):
        self.logs.append(log)
        return log


class PrivacyServiceTests(unittest.TestCase):
    def setUp(self):
        self.user_id = uuid.uuid4()
        self.profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=self.user_id, address="Address", blood_type="A+", share_health_data=True
        )
        self.user = SimpleNamespace(
            id=self.user_id,
            role=UserRole.PATIENT,
            name="Patient",
            is_active=True,
            session_version=2,
        )
        self.storage_directory = tempfile.TemporaryDirectory()
        self.storage = LocalFileStorage(self.storage_directory.name)
        self.file_key = "health_documents/profile/report.pdf"
        path = self.storage.path_for(self.file_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"report")
        self.privacy = FakePrivacyRepository([self.file_key])
        self.audits = FakeAuditRepository()
        self.service = PrivacyService(
            self.privacy,
            FakeProfiles(patient=self.profile),
            self.audits,
            self.storage,
        )

    def tearDown(self):
        self.storage_directory.cleanup()

    def test_patient_erasure_deletes_health_files_revokes_sessions_and_anonymizes_account(self):
        self.service.erase_account(self.user)

        self.assertEqual(self.privacy.erased_patient_id, self.profile.id)
        self.assertEqual(self.privacy.revoked_user_id, self.user_id)
        self.assertFalse(self.storage.path_for(self.file_key).exists())
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.name, "Cuenta eliminada")
        self.assertFalse(self.profile.share_health_data)
        self.assertEqual(self.audits.logs[0].accion.value, "eliminacion")
        self.assertEqual(self.audits.logs[0].entidad, "user")
        self.assertEqual(self.audits.logs[0].patient_id, self.profile.id)

    def test_professional_erasure_anonymizes_professional_account(self):
        professional_id = uuid.uuid4()
        professional = SimpleNamespace(
            id=professional_id,
            role=UserRole.PROFESSIONAL,
            name="Professional",
            is_active=True,
            session_version=1,
        )
        profile = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=professional_id,
            specialty="Cardiology",
            license_number="LIC-1",
            is_accepting_new_patients=True,
            telehealth_enabled=True,
        )
        privacy = FakePrivacyRepository()
        service = PrivacyService(
            privacy,
            FakeProfiles(professional=profile),
            self.audits,
            self.storage,
        )

        service.erase_account(professional)

        self.assertIsNone(privacy.erased_patient_id)
        self.assertEqual(profile.specialty, "Cuenta eliminada")
        self.assertFalse(professional.is_active)
        self.assertEqual(self.audits.logs[-1].patient_id, None)


if __name__ == "__main__":
    unittest.main()