import io
import tempfile
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import AppointmentStatus, Prescription, UserRole
from app.schemas.prescriptions import PrescriptionAuthorizationCreate, PrescriptionMetadata, PatientPrescriptionResponse
from pydantic import ValidationError
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
        prescription.created_at = datetime.now(timezone.utc)
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

    def upload(self, *args, metadata=None):
        return self.service.upload(*args, metadata=metadata or PrescriptionMetadata(
            tipo="medicacion", titulo="Medicamento de prueba", fecha_emision=date(2026, 9, 29)))

    def test_metadata_is_stored_and_replaced_in_same_record(self):
        args = (self.professional_id, self.professional, self.appointment_id)
        first = self.upload(*args, io.BytesIO(b"pdf"), "recipe.pdf", "application/pdf", None,
            metadata=PrescriptionMetadata(tipo="medicacion", titulo="  Dos medicamentos  ",
                fecha_emision=date(2026, 9, 29), fecha_caducidad=date(2026, 10, 29), codigo="  EXT-123  "))
        first_id = first.id
        self.assertEqual(first.titulo, "Dos medicamentos")
        self.assertEqual(first.codigo, "EXT-123")
        self.assertEqual(first.fecha_caducidad, date(2026, 10, 29))
        replacement = self.upload(*args, io.BytesIO(b"image"), "request.png", "image/png", "Prueba solicitada",
            metadata=PrescriptionMetadata(tipo="prueba", titulo="Solicitud de analítica", fecha_emision=date(2026, 9, 29)))
        self.assertEqual(replacement.id, first_id)
        self.assertEqual(replacement.tipo, "prueba")
        self.assertEqual(replacement.titulo, "Solicitud de analítica")
        self.assertIsNone(replacement.fecha_caducidad)
        self.assertIsNone(replacement.codigo)
        self.assertTrue(replacement.file_url.endswith('.png'))

    def test_metadata_rejects_invalid_dates_blank_title_and_unknown_type(self):
        valid = dict(tipo="prueba", titulo="Analítica", fecha_emision="2026-09-29")
        for change in ({"fecha_caducidad": "2026-09-28"}, {"titulo": "   "}, {"tipo": "invalid"}, {"codigo": "x" * 101}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                PrescriptionMetadata(**{**valid, **change})
        self.assertEqual(PrescriptionMetadata(**valid, fecha_caducidad="2026-09-29").fecha_caducidad, date(2026, 9, 29))

    def test_upload_api_requires_metadata_validates_dates_and_returns_saved_fields(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.prescriptions import router
        from app.api import deps
        self.appointment.end_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.appointment.start_time = self.appointment.end_time - timedelta(minutes=30)
        self.appointment.appointment_reason = "Revisión"
        app = FastAPI()
        app.include_router(router)
        def provide(value):
            return lambda: value
        for dependency, value in (
            (deps.get_current_user, self.professional), (deps.get_appointment_repository, self.appointments),
            (deps.get_profile_repository, self.profiles), (deps.get_prescription_repository, self.prescriptions),
            (deps.get_file_storage, self.storage), (deps.get_audit_repository, None),
        ):
            app.dependency_overrides[dependency] = provide(value)
        client = TestClient(app)
        path = f'/professionals/{self.professional_id}/appointments/{self.appointment_id}/prescription'
        files = {"file": ("recipe.pdf", b"%PDF test", "application/pdf")}
        self.assertEqual(client.post(path, files=files).status_code, 422)
        data = {"tipo": "prueba", "titulo": "Analítica", "fecha_emision": "2026-09-29", "fecha_caducidad": "2026-09-28"}
        self.assertEqual(client.post(path, files=files, data=data).status_code, 422)
        self.assertIsNone(self.prescriptions.prescription)
        data["fecha_caducidad"] = "2026-10-29"
        response = client.post(path, files=files, data=data)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["fecha_caducidad"], "2026-10-29")
        self.assertEqual(response.json()["titulo"], "Analítica")
        app.dependency_overrides[deps.get_current_user] = lambda: self.patient
        self.prescriptions.patient_view_rows = [(self.prescriptions.prescription, self.appointment, SimpleNamespace(name="Doctora"))]
        response = client.get(f'/patients/{self.patient_id}/prescriptions')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["prescriptions"][0]["tipo"], "prueba")
        self.assertEqual(response.json()["prescriptions"][0]["appointment_reason"], "Revisión")
        self.assertEqual(client.post(path, files=files, data=data).status_code, 403)

    def test_professional_can_upload_prescription_for_completed_appointment(self):
        result = self.upload(
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
            self.upload(
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
            self.upload(
                self.professional_id,
                self.professional,
                self.appointment_id,
                io.BytesIO(b"pdf"),
                "prescription.pdf",
                "application/pdf",
                None,
            )

    def test_professional_can_replace_prescription_inside_window(self):
        first = self.upload(
            self.professional_id,
            self.professional,
            self.appointment_id,
            io.BytesIO(b"first"),
            "prescription.pdf",
            "application/pdf",
            "First",
        )

        replacement = self.upload(
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

        result = self.upload(
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
        self.upload(
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
        appointment = SimpleNamespace(start_time=self.now - timedelta(days=1), appointment_reason="Revisión")
        prescription = SimpleNamespace(
            id=uuid.uuid4(),
            appointment_id=self.appointment_id,
            patient_id=self.profiles.patient_profile.id,
            professional_id=self.profiles.professional_profile.id,
            file_url="prescriptions/example.pdf",
            notas="Take daily",
            created_at=self.now,
            tipo="medicacion", titulo="Medicamento", fecha_emision=date(2026, 9, 28),
            fecha_caducidad=date(2026, 10, 28), codigo="EXT-1",
        )
        self.prescriptions.patient_view_rows = [(prescription, appointment, professional)]

        result = self.service.list_for_patient_view(self.patient_id, self.patient, self.professional_id)

        self.assertEqual(result[0]["professional_name"], "Dra. Ada Lovelace")
        self.assertEqual(result[0]["appointment_date"], appointment.start_time)
        self.assertEqual(result[0]["file_url"], "prescriptions/example.pdf")
        self.assertEqual(result[0]["titulo"], "Medicamento")
        self.assertEqual(result[0]["fecha_caducidad"], date(2026, 10, 28))
        self.assertEqual(result[0]["appointment_reason"], "Revisión")
        self.assertEqual(
            result[0]["download_url"],
            f"/patients/me/appointments/{self.appointment_id}/prescription",
        )

        # Historical files have no inferred clinical dates or title.
        for field in PrescriptionMetadata.model_fields:
            setattr(prescription, field, None)
        legacy = PatientPrescriptionResponse.model_validate(self.service.list_for_patient_view(self.patient_id, self.patient)[0])
        self.assertIsNone(legacy.fecha_emision)
        self.assertIsNone(legacy.fecha_caducidad)

    def test_patient_prescription_view_rejects_another_patient(self):
        with self.assertRaises(PrescriptionAccessError):
            self.service.list_for_patient_view(uuid.uuid4(), self.patient)

    def test_professional_downloads_linked_file_even_after_emission_window(self):
        uploaded = self.upload(self.professional_id, self.professional, self.appointment_id,
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
        self.upload(self.professional_id, self.professional, self.appointment_id,
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
