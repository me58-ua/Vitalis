import io
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import AppointmentStatus, Prescription, UserRole
from app.schemas.prescriptions import PrescriptionAuthorizationCreate
from app.services.file_storage import LocalFileStorage
from app.services.prescription_service import (
    PrescriptionAccessError,
    PrescriptionNotFoundError,
    PrescriptionService,
    PrescriptionValidationError,
)


class FakeAppointments:
    def __init__(self, appointment):
        self.appointment = appointment

    def get_appointment(self, appointment_id):
        if self.appointment and self.appointment.id == appointment_id:
            return self.appointment
        return None


class FakeProfiles:
    def __init__(self, patient_profile, professional_profile):
        self.patient_profile = patient_profile
        self.professional_profile = professional_profile

    def get_patient(self, user_id):
        return self.patient_profile if user_id == self.patient_profile.user_id else None

    def get_professional(self, user_id):
        return self.professional_profile if user_id == self.professional_profile.user_id else None


class FakePrescriptions:
    def __init__(self):
        self.prescription = None
        self.authorization = None
        self.patient_view_rows = []

    def get_by_appointment(self, appointment_id):
        if self.prescription and self.prescription.appointment_id == appointment_id:
            return self.prescription
        return None

    def get_authorization(self, appointment_id):
        if self.authorization and self.authorization.appointment_id == appointment_id:
            return self.authorization
        return None

    def list_for_patient_view(self, patient_user_id, professional_user_id=None):
        return self.patient_view_rows

    def create(self, prescription):
        prescription.id = uuid.uuid4()
        self.prescription = prescription
        return prescription

    def update(self, prescription, values):
        for field, value in values.items():
            setattr(prescription, field, value)
        return prescription

    def create_authorization(self, authorization):
        self.authorization = authorization
        return authorization

    def rollback(self):
        pass


class PrescriptionServiceTests(unittest.TestCase):
    def setUp(self):
        self.professional_id = uuid.uuid4()
        self.patient_id = uuid.uuid4()
        self.appointment_id = uuid.uuid4()
        self.now = datetime(2026, 9, 29, 18, tzinfo=timezone.utc)
        self.appointment = SimpleNamespace(
            id=self.appointment_id,
            patient_id=self.patient_id,
            professional_id=self.professional_id,
            end_time=self.now - timedelta(hours=1),
            status=AppointmentStatus.COMPLETED,
        )
        patient_profile = SimpleNamespace(id=uuid.uuid4(), user_id=self.patient_id)
        professional_profile = SimpleNamespace(id=uuid.uuid4(), user_id=self.professional_id)
        self.appointments = FakeAppointments(self.appointment)
        self.profiles = FakeProfiles(patient_profile, professional_profile)
        self.prescriptions = FakePrescriptions()
        self.storage_directory = tempfile.TemporaryDirectory()
        self.storage = LocalFileStorage(self.storage_directory.name)
        self.service = PrescriptionService(
            self.appointments,
            self.profiles,
            self.prescriptions,
            self.storage,
            now=lambda: self.now,
        )
        self.professional = SimpleNamespace(id=self.professional_id, role=UserRole.PROFESSIONAL)
        self.admin = SimpleNamespace(id=uuid.uuid4(), role=UserRole.ADMIN)
        self.patient = SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT)

    def tearDown(self):
        self.storage_directory.cleanup()

    def test_professional_can_upload_prescription_for_completed_appointment(self):
        result = self.service.upload(
            self.professional_id,
            self.professional,
            self.appointment_id,
            io.BytesIO(b"pdf"),
            "prescription.pdf",
            "application/pdf",
            "Take once daily",
        )

        self.assertEqual(result.patient_id, self.profiles.patient_profile.id)
        self.assertEqual(result.professional_id, self.profiles.professional_profile.id)
        self.assertEqual(result.notas, "Take once daily")
        self.assertTrue(self.storage.path_for(result.file_url).is_file())

    def test_upload_is_rejected_after_emission_window(self):
        self.appointment.end_time = self.now - timedelta(hours=9)

        with self.assertRaisesRegex(PrescriptionAccessError, "ventana de emisión de receta expirada"):
            self.service.upload(
                self.professional_id,
                self.professional,
                self.appointment_id,
                io.BytesIO(b"pdf"),
                "prescription.pdf",
                "application/pdf",
                None,
            )

    def test_upload_requires_completed_appointment(self):
        self.appointment.status = AppointmentStatus.CONFIRMED

        self.assertFalse(self.service.can_upload_prescription(self.appointment))
        with self.assertRaises(PrescriptionValidationError):
            self.service.upload(
                self.professional_id,
                self.professional,
                self.appointment_id,
                io.BytesIO(b"pdf"),
                "prescription.pdf",
                "application/pdf",
                None,
            )

    def test_professional_can_replace_prescription_inside_window(self):
        first = self.service.upload(
            self.professional_id,
            self.professional,
            self.appointment_id,
            io.BytesIO(b"first"),
            "prescription.pdf",
            "application/pdf",
            "First",
        )

        replacement = self.service.upload(
            self.professional_id,
            self.professional,
            self.appointment_id,
            io.BytesIO(b"replacement"),
            "prescription.pdf",
            "application/pdf",
            "Replacement",
        )

        self.assertEqual(replacement.id, first.id)
        self.assertEqual(replacement.notas, "Replacement")
        self.assertEqual(self.storage.path_for(first.file_url).read_bytes(), b"replacement")

    def test_admin_authorization_allows_late_upload(self):
        self.appointment.end_time = self.now - timedelta(hours=9)
        self.service.authorize_late_issue(
            self.appointment_id,
            self.admin,
            PrescriptionAuthorizationCreate(reason="Patient requested correction"),
        )

        result = self.service.upload(
            self.professional_id,
            self.professional,
            self.appointment_id,
            io.BytesIO(b"pdf"),
            "prescription.pdf",
            "application/pdf",
            None,
        )

        self.assertIsNotNone(result)

    def test_only_patient_of_appointment_can_download(self):
        self.service.upload(
            self.professional_id,
            self.professional,
            self.appointment_id,
            io.BytesIO(b"pdf"),
            "prescription.pdf",
            "application/pdf",
            None,
        )

        _, path = self.service.download_for_patient(self.appointment_id, self.patient)
        self.assertEqual(path.read_bytes(), b"pdf")

        with self.assertRaises(PrescriptionAccessError):
            self.service.download_for_patient(self.appointment_id, SimpleNamespace(id=uuid.uuid4()))

    def test_patient_prescription_view_includes_professional_and_appointment_details(self):
        professional = SimpleNamespace(name="Dra. Ada Lovelace")
        appointment = SimpleNamespace(start_time=self.now - timedelta(days=1))
        prescription = SimpleNamespace(
            id=uuid.uuid4(),
            appointment_id=self.appointment_id,
            patient_id=self.profiles.patient_profile.id,
            professional_id=self.profiles.professional_profile.id,
            file_url="prescriptions/example.pdf",
            notas="Take daily",
            created_at=self.now,
        )
        self.prescriptions.patient_view_rows = [(prescription, appointment, professional)]

        result = self.service.list_for_patient_view(self.patient_id, self.patient, self.professional_id)

        self.assertEqual(result[0]["professional_name"], "Dra. Ada Lovelace")
        self.assertEqual(result[0]["appointment_date"], appointment.start_time)
        self.assertEqual(result[0]["file_url"], "prescriptions/example.pdf")
        self.assertEqual(
            result[0]["download_url"],
            f"/patients/me/appointments/{self.appointment_id}/prescription",
        )

    def test_patient_prescription_view_rejects_another_patient(self):
        with self.assertRaises(PrescriptionAccessError):
            self.service.list_for_patient_view(uuid.uuid4(), self.patient)

    def test_professional_downloads_linked_file_even_after_emission_window(self):
        uploaded = self.service.upload(self.professional_id, self.professional, self.appointment_id,
            io.BytesIO(b"linked-pdf"), "prescription.pdf", "application/pdf", None)
        self.appointment.end_time = self.now - timedelta(days=30)
        result, path = self.service.download_for_professional(self.professional_id, self.appointment_id, self.professional)
        self.assertEqual(result.id, uploaded.id)
        self.assertEqual(path.read_bytes(), b"linked-pdf")

    def test_professional_download_rejects_identity_or_ownership_mismatch(self):
        with self.assertRaises(PrescriptionAccessError):
            self.service.download_for_professional(uuid.uuid4(), self.appointment_id, self.professional)
        self.appointment.professional_id = uuid.uuid4()
        with self.assertRaises(PrescriptionAccessError):
            self.service.download_for_professional(self.professional_id, self.appointment_id, self.professional)

    def test_professional_download_reports_missing_appointment_recipe_or_file(self):
        with self.assertRaises(PrescriptionNotFoundError):
            self.service.download_for_professional(self.professional_id, uuid.uuid4(), self.professional)
        with self.assertRaises(PrescriptionNotFoundError):
            self.service.download_for_professional(self.professional_id, self.appointment_id, self.professional)

        self.prescriptions.prescription = SimpleNamespace(appointment_id=self.appointment_id, file_url='prescriptions/missing.pdf')
        with self.assertRaises(PrescriptionNotFoundError):
            self.service.download_for_professional(self.professional_id, self.appointment_id, self.professional)

    def test_download_route_streams_file_and_rejects_patient_role(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.prescriptions import router
        from app.api import deps
        self.service.upload(self.professional_id, self.professional, self.appointment_id,
            io.BytesIO(b"downloaded-pdf"), "prescription.pdf", "application/pdf", None)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[deps.get_current_user] = lambda: self.professional
        app.dependency_overrides[deps.get_appointment_repository] = lambda: self.appointments
        app.dependency_overrides[deps.get_profile_repository] = lambda: self.profiles
        app.dependency_overrides[deps.get_prescription_repository] = lambda: self.prescriptions
        app.dependency_overrides[deps.get_file_storage] = lambda: self.storage
        client = TestClient(app)
        path = f'/professionals/{self.professional_id}/appointments/{self.appointment_id}/prescription'
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"downloaded-pdf")
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertIn('attachment;', response.headers['content-disposition'])
        app.dependency_overrides[deps.get_current_user] = lambda: self.patient
        self.assertEqual(client.get(path).status_code, 403)


if __name__ == "__main__":
    unittest.main()
