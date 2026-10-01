import io
import tempfile
import unittest
import uuid
from types import SimpleNamespace

from app.models import HealthDocumentType, UserRole
from app.services.file_storage import LocalFileStorage
from app.services.health_document_service import (
    HealthDocumentAccessError,
    HealthDocumentService,
    HealthDocumentValidationError,
)


class FakeDocuments:
    def __init__(self):
        self.items = {}

    def create(self, document):
        self.items[document.id] = document
        return document

    def get(self, document_id):
        return self.items.get(document_id)

    def list_for_patient(self, patient_id):
        return [item for item in self.items.values() if item.patient_id == patient_id]


class FakeProfiles:
    def __init__(self, patient):
        self.patient = patient

    def get_patient(self, user_id):
        return self.patient if user_id == self.patient.user_id else None


class FakeAppointments:
    def __init__(self, shared=True):
        self.shared = shared

    def has_shared_appointment(self, patient_id, professional_id):
        return self.shared


class HealthDocumentServiceTests(unittest.TestCase):
    def setUp(self):
        self.patient_user_id = uuid.uuid4()
        self.professional_user_id = uuid.uuid4()
        self.patient_profile = SimpleNamespace(
            id=uuid.uuid4(), user_id=self.patient_user_id, share_health_data=True
        )
        self.patient = SimpleNamespace(id=self.patient_user_id, role=UserRole.PATIENT)
        self.professional = SimpleNamespace(id=self.professional_user_id, role=UserRole.PROFESSIONAL)
        self.documents = FakeDocuments()
        self.appointments = FakeAppointments()
        self.storage_directory = tempfile.TemporaryDirectory()
        self.storage = LocalFileStorage(self.storage_directory.name)
        self.service = HealthDocumentService(
            self.documents,
            FakeProfiles(self.patient_profile),
            self.appointments,
            self.storage,
            max_file_size=10,
        )

    def tearDown(self):
        self.storage_directory.cleanup()

    def test_patient_can_upload_document_without_appointment(self):
        self.appointments.shared = False

        document = self.service.upload(
            self.patient,
            io.BytesIO(b"pdf"),
            "external-report.pdf",
            "application/pdf",
            HealthDocumentType.REPORT,
            "Informe externo",
        )

        self.assertEqual(document.patient_id, self.patient_profile.id)
        self.assertEqual(document.tipo, HealthDocumentType.REPORT)
        self.assertEqual(self.storage.path_for(document.file_url).read_bytes(), b"pdf")

    def test_upload_rejects_non_pdf_or_image(self):
        with self.assertRaises(HealthDocumentValidationError):
            self.service.upload(
                self.patient,
                io.BytesIO(b"text"),
                "notes.txt",
                "text/plain",
                HealthDocumentType.OTHER,
                None,
            )

    def test_upload_rejects_file_over_limit(self):
        with self.assertRaises(HealthDocumentValidationError):
            self.service.upload(
                self.patient,
                io.BytesIO(b"01234567890"),
                "report.pdf",
                "application/pdf",
                HealthDocumentType.REPORT,
                None,
            )
        self.assertEqual(self.documents.items, {})

    def test_professional_requires_shared_appointment_and_consent(self):
        document = self.service.upload(
            self.patient,
            io.BytesIO(b"image"),
            "result.png",
            "image/png",
            HealthDocumentType.LABORATORY,
            None,
        )

        self.assertEqual(
            self.service.list_for_professional(self.patient_user_id, self.professional_user_id), [document]
        )

        self.patient_profile.share_health_data = False
        with self.assertRaises(HealthDocumentAccessError):
            self.service.list_for_professional(self.patient_user_id, self.professional_user_id)

        self.patient_profile.share_health_data = True
        self.appointments.shared = False
        with self.assertRaises(HealthDocumentAccessError):
            self.service.list_for_professional(self.patient_user_id, self.professional_user_id)

    def test_patient_cannot_download_another_patient_document(self):
        document = self.service.upload(
            self.patient,
            io.BytesIO(b"pdf"),
            "report.pdf",
            "application/pdf",
            HealthDocumentType.REPORT,
            None,
        )

        with self.assertRaises(HealthDocumentAccessError):
            self.service.download_for_patient(document.id, SimpleNamespace(id=uuid.uuid4()))


if __name__ == "__main__":
    unittest.main()