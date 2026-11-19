"""Search isolation against actual SQL queries, using synthetic SQLite fixtures."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models import HealthDocument, HealthDocumentType, UserRole
from app.repositories.health_document_repository import HealthDocumentRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.services.health_document_service import (
    HealthDocumentAccessError, HealthDocumentService, HealthDocumentValidationError,
)


class DocumentSearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE patient_profiles (id CHAR(32) PRIMARY KEY, user_id CHAR(32), share_health_data BOOLEAN)")
            connection.exec_driver_sql(
                "CREATE TABLE appointments (id CHAR(32) PRIMARY KEY, patient_id CHAR(32), "
                "professional_id CHAR(32), health_sharing VARCHAR(5), created_at DATETIME)"
            )
        HealthDocument.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.patient = SimpleNamespace(id=uuid4(), role=UserRole.PATIENT)
        self.other = SimpleNamespace(id=uuid4(), role=UserRole.PATIENT)
        self.professional = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL)
        self.profiles = {}
        for user in (self.patient, self.other):
            profile_id = uuid4()
            self.profiles[user.id] = profile_id
            self.db.connection().exec_driver_sql(
                "INSERT INTO patient_profiles VALUES (?, ?, ?)", (profile_id.hex, user.id.hex, True)
            )
        self.service = HealthDocumentService(HealthDocumentRepository(self.db), None, None, None, 100)

    def document(self, user, description, kind=HealthDocumentType.REPORT):
        document = HealthDocument(
            id=uuid4(), patient_id=self.profiles[user.id], descripcion=description,
            tipo=kind, file_url="private/path-not-searchable.pdf", fecha_subida=datetime.now(timezone.utc),
        )
        self.db.add(document)
        self.db.flush()
        return document

    def appointment(self, patient, scope, created_at, professional=None):
        self.db.connection().exec_driver_sql(
            "INSERT INTO appointments VALUES (?, ?, ?, ?, ?)",
            (uuid4().hex, patient.id.hex, (professional or self.professional).id.hex, scope, created_at),
        )

    def test_patient_search_is_case_insensitive_and_never_leaks_other_documents(self):
        own = self.document(self.patient, "Informe de revisión")
        self.document(self.other, "Informe de revisión")
        result = self.service.search(self.patient, "  INFORME  ")
        self.assertEqual([item.id for item in result.documents], [own.id])
        self.assertEqual(result.documents[0].patient_user_id, self.patient.id)
        self.assertNotIn("file_url", result.documents[0].model_dump())
        self.assertEqual(self.service.search(self.patient, "private").total, 0)

    def test_professional_requires_both_shared_appointment_and_current_consent(self):
        self.document(self.patient, "Informe")
        self.document(self.other, "Informe")
        self.assertEqual(self.service.search(self.professional, "Informe").total, 0)
        self.appointment(self.patient, None, "2026-01-01")
        self.assertEqual(self.service.search(self.professional, "Informe").total, 0)
        self.appointment(self.patient, "full", "2026-01-02")
        self.appointment(self.patient, None, "2026-01-03")
        self.assertEqual(self.service.search(self.professional, "Informe").total, 1)
        self.appointment(self.patient, "basic", "2026-01-04")
        other_professional = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL)
        self.appointment(self.patient, "full", "2026-01-05", other_professional)
        self.assertEqual(self.service.search(self.professional, "Informe").total, 0)
        self.assertEqual(self.service.search(other_professional, "Informe").total, 1)
        profile = SimpleNamespace(user_id=self.patient.id, share_health_data=True)
        appointments = AppointmentRepository(self.db)
        self.assertEqual(appointments.health_sharing_scope(profile, self.professional.id), "basic")
        self.appointment(self.patient, "none", "2026-01-06")
        self.assertEqual(appointments.health_sharing_scope(profile, self.professional.id), "none")
        self.db.connection().exec_driver_sql(
            "UPDATE patient_profiles SET share_health_data = 0 WHERE user_id = ?", (self.patient.id.hex,)
        )
        self.assertEqual(self.service.search(other_professional, "Informe").total, 0)

    def test_literal_wildcards_type_filter_pagination_and_null_description(self):
        self.document(self.patient, "Informe 100%")
        self.document(self.patient, "Informe normal")
        self.document(self.patient, None, HealthDocumentType.LABORATORY)
        self.assertEqual(self.service.search(self.patient, "%").total, 1)
        self.assertEqual(self.service.search(self.patient, "_").total, 0)
        result = self.service.search(self.patient, "informe", page_size=1)
        next_page = self.service.search(self.patient, "informe", page=2, page_size=1)
        self.assertEqual(result.total, 2)
        self.assertNotEqual(result.documents[0].id, next_page.documents[0].id)
        self.assertEqual(self.service.search(self.patient, "analitica").total, 1)
        self.assertEqual(self.service.search(self.patient, "informe", HealthDocumentType.LABORATORY).total, 0)

    def test_invalid_query_and_unauthorized_role(self):
        for query in ("   ", "x" * 101):
            with self.assertRaises(HealthDocumentValidationError):
                self.service.search(self.patient, query)
        with self.assertRaises(HealthDocumentAccessError):
            self.service.search(SimpleNamespace(id=uuid4(), role=UserRole.ADMIN), "informe")

    def test_openapi_search_and_logout_contract(self):
        paths = app.openapi()["paths"]
        self.assertIn("204", paths["/auth/logout"]["post"]["responses"])
        parameters = paths["/health/documents/search"]["get"]["parameters"]
        self.assertEqual({parameter["name"] for parameter in parameters}, {"q", "tipo", "page", "page_size"})

    def test_http_authentication_validation_and_search_response(self):
        from app.api.deps import (
            get_current_user, get_health_document_repository, get_profile_repository,
            get_appointment_repository, get_file_storage,
        )
        client = TestClient(app)  # No lifespan/background dispatcher or production DB queries.
        self.addCleanup(client.close)
        self.assertEqual(client.get("/health/documents/search", params={"q": "informe"}).status_code, 401)
        self.assertEqual(client.post("/auth/logout").status_code, 401)
        previous = app.dependency_overrides.copy()
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        app.dependency_overrides.update({
            get_current_user: lambda: self.patient,
            get_health_document_repository: lambda: HealthDocumentRepository(self.db),
            get_profile_repository: lambda: None,
            get_appointment_repository: lambda: None,
            get_file_storage: lambda: None,
        })
        self.document(self.patient, "Informe sintético")
        self.document(self.other, "Informe privado de otra cuenta")
        result = client.get("/health/documents/search", params={"q": "informe", "page_size": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["total"], 1)
        self.assertNotIn("file_url", result.json()["documents"][0])
        for params in ({"q": " "}, {"q": "x", "page": 0}, {"q": "x", "tipo": "invalid"}):
            self.assertEqual(client.get("/health/documents/search", params=params).status_code, 422)


if __name__ == "__main__":
    unittest.main()
