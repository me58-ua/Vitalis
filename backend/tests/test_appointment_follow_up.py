import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
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
from app.models import (
    Appointment, AppointmentNote, AppointmentStatus, AppointmentStatusHistory, AppointmentType,
    AuditLog, EmailStatus, Notification, Prescription, ProfessionalProfile, User, UserRole,
)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointments import AppointmentCancelRequest, ProfessionalAppointmentStatusUpdate
from app.services.appointment_service import AppointmentService
from app.services.notification_dispatcher import NotificationDispatcher


class AppointmentFollowUpTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        metadata = MetaData()
        with self.engine.begin() as connection:
            for model in (User, ProfessionalProfile, Appointment, AppointmentNote, AppointmentStatusHistory,
                          AuditLog, Notification, Prescription):
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

    def test_patient_cancellation_is_visible_in_professional_agenda(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            appointment = db.get(Appointment, self.appointment_id)
            appointment.status = AppointmentStatus.CONFIRMED
            appointment.start_time = now + timedelta(days=2)
            appointment.end_time = appointment.start_time + timedelta(minutes=30)
            appointment.appointment_reason = "Revisión"
            db.commit()
            repo = AppointmentRepository(db)
            service = AppointmentService(repo, UserRepository(db), ProfessionalRepository(db))
            patient = db.get(User, self.patient_id)
            for _ in range(2):
                service.cancel_appointment(self.patient_id, self.appointment_id, patient,
                                           AppointmentCancelRequest(), enforce_patient_notice=True)
            db.commit()

            self.assertEqual(repo.list_patient_appointments(self.patient_id, 0, 20, confirmed_only=True), ([], 0))
            rows, total = repo.list_for_professional(self.professional_id, now, now, now + timedelta(days=7),
                                                    None, False, 0, 20)
            self.assertEqual(total, 1)
            self.assertEqual(rows[0]["status"], AppointmentStatus.CANCELLED)
            self.assertEqual(rows[0]["appointment_reason"], "Revisión")
            self.assertIsNone(rows[0]["cancellation_reason"])
            self.assertEqual(len(list(db.scalars(select(AppointmentStatusHistory)))), 1)

    def test_patient_history_filters_completed_consultations_by_madrid_date_and_doctor(self):
        before_midnight = datetime(2025, 3, 29, 22, 30, tzinfo=timezone.utc)
        after_midnight = before_midnight + timedelta(hours=1)
        next_day = datetime(2025, 3, 30, 22, 0, tzinfo=timezone.utc)
        older_id, newest_id, cancelled_id, confirmed_id, other_doctor_id = (uuid4() for _ in range(5))
        with Session(self.engine) as db:
            existing = db.get(Appointment, self.appointment_id)
            existing.start_time = after_midnight
            existing.end_time = after_midnight + timedelta(minutes=20)
            existing.appointment_reason = "Revisión"
            note = db.scalar(select(AppointmentNote).where(AppointmentNote.appointment_id == self.appointment_id))
            note.shared_diagnosis, note.shared_notes, note.clinical_notes = "Shared diagnosis", "Shared notes", "Private details"
            db.add(User(id=other_doctor_id, name="Other doctor", dni="Doctor", username="doctor",
                        email="doctor@example.test", tel="000", birth_date=date(1990, 1, 1), password_hash="unused",
                        role=UserRole.PROFESSIONAL))
            for identifier, patient, doctor, start, status in (
                (older_id, self.patient_id, other_doctor_id, before_midnight, AppointmentStatus.COMPLETED),
                (newest_id, self.patient_id, self.professional_id, next_day, AppointmentStatus.COMPLETED),
                (cancelled_id, self.patient_id, self.professional_id, next_day + timedelta(hours=1), AppointmentStatus.CANCELLED),
                (confirmed_id, self.patient_id, self.professional_id, after_midnight, AppointmentStatus.CONFIRMED),
                (uuid4(), uuid4(), self.professional_id, after_midnight, AppointmentStatus.COMPLETED),
            ):
                db.add(Appointment(id=identifier, patient_id=patient, professional_id=doctor, start_time=start,
                                   end_time=start + timedelta(minutes=15), status=status))
            db.add(Prescription(appointment_id=self.appointment_id, patient_id=uuid4(), professional_id=uuid4(),
                                file_url="private/fixture.pdf"))
            db.commit()
            rows, total = AppointmentRepository(db).list_patient_appointments(self.patient_id, 0, 20, confirmed_only=True)
            self.assertEqual(total, 1)
            self.assertEqual([item["id"] for item in rows], [confirmed_id])

        path = "/patients/me/appointments/history"
        self.assertEqual(self.http.get(path).status_code, 403)
        self.user = SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT)
        response = self.http.get(path, params={"page_size": 2})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json()["total"], 4)
        self.assertEqual([item["appointment_id"] for item in response.json()["appointments"]],
                         [str(cancelled_id), str(newest_id)])
        cancelled = self.http.get(f"/patients/me/appointments/{cancelled_id}/follow-up").json()
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIsNone(cancelled["shared_notes"])
        self.assertEqual(self.http.get(f"/patients/me/appointments/{confirmed_id}/follow-up").status_code, 404)
        single = self.http.get(path, params={"from_date": "2025-03-30", "doctor": "pROFESS"}).json()
        self.assertEqual(single["total"], 1)
        row = single["appointments"][0]
        self.assertEqual(row["appointment_reason"], "Revisión")
        self.assertEqual(row["shared_diagnosis"], "Shared diagnosis")
        self.assertTrue(row["has_prescription"])
        self.assertNotIn("clinical_notes", row)
        self.assertNotIn("file_url", row)
        self.assertEqual(self.http.get(self.detail).json()["shared_notes"], "Shared notes")
        span = self.http.get(path, params={"from_date": "2025-03-29", "to_date": "2025-03-30"}).json()
        self.assertEqual([item["appointment_id"] for item in span["appointments"]],
                         [str(self.appointment_id), str(older_id)])
        self.assertEqual(self.http.get(path, params={"doctor": "%"}).json()["total"], 0)
        self.assertEqual(self.http.get(path, params={"from_date": "2025-03-30", "to_date": "2025-03-29"}).status_code, 422)

    def test_started_in_person_visit_can_be_completed_from_patient_history(self):
        with Session(self.engine) as db:
            appointment = db.get(Appointment, self.appointment_id)
            appointment.type = AppointmentType.IN_PERSON
            appointment.status = AppointmentStatus.CONFIRMED
            db.commit()
            repo = AppointmentRepository(db)
            now = datetime.now(timezone.utc)
            for patient_id, expected in ((None, 0), (self.patient_id, 1)):
                _, total = repo.list_past_for_professional(
                    self.professional_id, now, patient_id, None, None, None, None, 0, 10,
                )
                self.assertEqual(total, expected)

        self.assertEqual(self.http.get(self.editor).status_code, 409)
        with Session(self.engine) as db:
            service = AppointmentService(AppointmentRepository(db), UserRepository(db), ProfessionalRepository(db))
            for _ in range(2):
                completed = service.update_status_as_professional(
                    self.professional_id, self.user, self.appointment_id,
                    ProfessionalAppointmentStatusUpdate(status=AppointmentStatus.COMPLETED),
                )
                self.assertEqual(completed.status, AppointmentStatus.COMPLETED)
            db.commit()
            self.assertEqual(len(list(db.scalars(select(AppointmentStatusHistory)))), 1)
        response = self.http.put(self.editor, json={
            "shared_diagnosis": "Diagnosis", "shared_notes": None, "clinical_notes": "Private notes",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.user = SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT)
        response = self.http.get(self.detail)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["shared_diagnosis"], "Diagnosis")
        self.assertNotIn("Private notes", response.text)

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
            self.assertTrue(notices[0].email_required)
            self.assertEqual(notices[0].email_status, EmailStatus.PENDING)
            self.assertNotIn("Shared diagnosis", notices[0].message)
            self.assertNotIn("Shared instructions", notices[0].message)
            rows = AppointmentRepository(db).patient_follow_ups(self.patient_id)
            self.assertEqual(len(rows), 1)
            self.assertNotIn("clinical_notes", rows[0])
            history, _ = AppointmentRepository(db).list_past_for_professional(
                self.professional_id, datetime.now(timezone.utc), None, None, None, None, None, 0, 10,
            )
            self.assertEqual(history[0][2].clinical_notes, "Author only")

    @patch("app.services.notification_dispatcher.send_product_notification_email", return_value=True)
    def test_optional_shared_notes_queue_one_generic_email_to_the_patient(self, send):
        notes = {"shared_diagnosis": None, "shared_notes": "Sensitive instructions", "clinical_notes": None}
        for _ in range(2):
            self.assertEqual(self.http.put(self.editor, json=notes).status_code, 200)
        self.assertEqual(self.http.put(self.editor, json={**notes, "shared_notes": None}).status_code, 200)

        with Session(self.engine) as db:
            dispatcher = NotificationDispatcher(NotificationRepository(db), UserRepository(db))
            self.assertEqual(dispatcher.run_once(), 1)
            self.assertEqual(dispatcher.run_once(), 0)
            notice = db.scalars(select(Notification)).one()
            self.assertEqual(notice.email_status, EmailStatus.SENT)
            self.assertIsNone(notice.read_at)

        send.assert_called_once()
        email, title, message, link = send.call_args.args
        self.assertEqual(email, "Patient@example.test")
        self.assertIn("notas", message)
        self.assertNotIn("Sensitive instructions", f"{title} {message}")
        self.assertTrue(link.endswith(f"/patientPanel/misCitas/{self.appointment_id}"))
