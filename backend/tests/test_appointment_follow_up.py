import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable

from app.api import appointments, professionals
from app.api.deps import get_current_user
from app.database import get_db
from app.models import Appointment, AppointmentNote, AppointmentStatus, AuditLog, Notification, Prescription, User, UserRole
from app.repositories.appointment_repository import AppointmentRepository


class AppointmentFollowUpTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        metadata = MetaData()
        with self.engine.begin() as connection:
            for model in (User, Appointment, AppointmentNote, AuditLog, Notification, Prescription):
                table = model.__table__.to_metadata(metadata)
                for constraint in list(table.constraints):
                    if isinstance(constraint, ExcludeConstraint):
                        table.constraints.remove(constraint)
                connection.execute(CreateTable(table, include_foreign_key_constraints=[]))
        self.professional_id, self.patient_id, self.appointment_id = uuid4(), uuid4(), uuid4()
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            for name, user_id, role in (
                ("Professional", self.professional_id, UserRole.PROFESSIONAL),
                ("Patient", self.patient_id, UserRole.PATIENT),
            ):
                db.add(User(id=user_id, name=name, dni=name, username=name, email=f"{name}@example.test",
                            tel="000", birth_date=date(1990, 1, 1), password_hash="unused", role=role))
            db.add(Appointment(id=self.appointment_id, patient_id=self.patient_id, professional_id=self.professional_id,
                               start_time=now - timedelta(minutes=15), end_time=now + timedelta(minutes=15),
                               status=AppointmentStatus.COMPLETED))
            db.add(AppointmentNote(appointment_id=self.appointment_id, professional_id=self.professional_id,
                                   diagnosis="Legacy diagnosis", patient_summary="Legacy summary"))
            db.commit()

        def database():
            with Session(self.engine) as db:
                yield db
                db.commit()

        self.user = SimpleNamespace(id=self.professional_id, role=UserRole.PROFESSIONAL)
        app = FastAPI()
        app.include_router(professionals.router)
        app.include_router(appointments.patient_router)
        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.http = TestClient(app)
        self.editor = f"/professionals/me/appointments/{self.appointment_id}/follow-up"
        self.detail = f"/patients/me/appointments/{self.appointment_id}/follow-up"

    def test_private_notes_and_legacy_fields_stay_out_of_patient_views(self):
        notes = {"clinical_notes": "Author only", "shared_diagnosis": None, "shared_notes": None}
        self.assertEqual(self.http.put(self.editor, json=notes).status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Notification))), [])
            self.assertEqual(AppointmentRepository(db).patient_follow_ups(self.patient_id), [])

        notes.update(shared_diagnosis="Shared diagnosis", shared_notes="Shared instructions")
        self.assertEqual(self.http.put(self.editor, json=notes).status_code, 200)
        self.assertEqual(self.http.put(self.editor, json=notes).status_code, 200)
        self.assertEqual(self.http.get(self.editor).json()["clinical_notes"], "Author only")
        self.user = SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT)
        response = self.http.get(self.detail)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["shared_diagnosis"], "Shared diagnosis")
        self.assertEqual(response.json()["shared_notes"], "Shared instructions")
        for private in ("clinical_notes", "Author only", "Legacy diagnosis", "Legacy summary"):
            self.assertNotIn(private, response.text)
        self.assertEqual(self.http.get(self.editor).status_code, 403)
        self.user.id = uuid4()
        self.assertEqual(self.http.get(self.detail).status_code, 404)
        self.user.role = UserRole.PROFESSIONAL
        self.assertEqual(self.http.put(self.editor, json=notes).status_code, 404)
        with Session(self.engine) as db:
            notices = list(db.scalars(select(Notification)))
            self.assertEqual(len(notices), 1)
            self.assertEqual(notices[0].recipient_id, self.patient_id)
            self.assertEqual(notices[0].entity_id, self.appointment_id)
            self.assertFalse(notices[0].email_required)
            self.assertNotIn("Shared diagnosis", notices[0].message)
            rows = AppointmentRepository(db).patient_follow_ups(self.patient_id)
            self.assertEqual(len(rows), 1)
            self.assertNotIn("clinical_notes", rows[0])
            history, _ = AppointmentRepository(db).list_past_for_professional(
                self.professional_id, datetime.now(timezone.utc), None, None, None, None, None, 0, 10,
            )
            self.assertEqual(history[0][2].clinical_notes, "Author only")
