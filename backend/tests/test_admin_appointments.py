import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, event, func, select
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import User, UserRole, PatientProfile, Appointment, AppointmentStatus, AppointmentType, AuditLog, AppointmentStatusHistory, Notification
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.admin_appointments import AdminAppointmentsQuery
from app.services.admin_appointment_service import AdminAppointmentQueryService


class AdminAppointmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        event.listen(self.engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
        metadata = MetaData()
        for model in (User, PatientProfile, Appointment, AuditLog, AppointmentStatusHistory, Notification):
            table = model.__table__.to_metadata(metadata)
            for constraint in list(table.constraints):
                if isinstance(constraint, ExcludeConstraint):
                    table.constraints.remove(constraint)  # PostgreSQL overlap protection is tested against Docker separately.
        metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)
        self.users = {}
        for role in UserRole:
            user = User(id=uuid4(), name=role.value, dni=role.value, username=role.value,
                        email=role.value + "@example.invalid", password_hash="test-only", role=role,
                        tel="000", birth_date=date(1990, 1, 1), is_active=True)
            self.users[role] = user
            self.db.add(user)
        self.db.flush()
        self.profile = PatientProfile(user_id=self.users[UserRole.PATIENT].id)
        self.db.add(self.profile)
        self.now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
        self.rows = []
        for delta, status in [(1, AppointmentStatus.PENDING), (2, AppointmentStatus.CONFIRMED), (-1, AppointmentStatus.PENDING), (3, AppointmentStatus.CANCELLED), (4, AppointmentStatus.COMPLETED), (60, AppointmentStatus.PENDING)]:
            row = Appointment(patient_id=self.users[UserRole.PATIENT].id, professional_id=self.users[UserRole.PROFESSIONAL].id,
                              start_time=self.now + timedelta(hours=delta), end_time=self.now + timedelta(hours=delta, minutes=30),
                              status=status, type=AppointmentType.VIDEO)
            self.rows.append(row); self.db.add(row)
        self.db.flush()
        self.actor = SimpleNamespace(id=self.users[UserRole.ADMIN].id, role=UserRole.ADMIN)
        previous = app.dependency_overrides.copy()
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.actor
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_month_only_future_pending_confirmed_and_summary_fields(self):
        service = AdminAppointmentQueryService(AppointmentRepository(self.db))
        result = service.list(AdminAppointmentsQuery(upcoming_month=True), now=self.now)
        self.assertEqual(result.total, 2)
        self.assertEqual({item.id for item in result.appointments}, {self.rows[0].id, self.rows[1].id})
        payload = self.client.get("/admin/appointments").json()
        self.assertEqual(payload["total"], 6)
        self.assertEqual(set(payload["appointments"][0]), {
            "id", "patient_id", "patient_name", "professional_id", "professional_name",
            "start_time", "end_time", "type", "status", "appointment_reason", "cancellation_reason",
        })
        self.assertNotEqual(self.profile.id, self.users[UserRole.PATIENT].id)

    def test_filter_count_pagination_and_dates(self):
        params = {"patient_id": str(self.users[UserRole.PATIENT].id), "professional_id": str(self.users[UserRole.PROFESSIONAL].id),
                  "from_date": "2026-10-30", "to_date": "2026-10-30", "page_size": 1}
        first = self.client.get("/admin/appointments", params=params)
        second = self.client.get("/admin/appointments", params={**params, "page": 2})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["total"], 5)
        self.assertNotEqual(first.json()["appointments"][0]["id"], second.json()["appointments"][0]["id"])
        self.assertEqual(self.client.get("/admin/appointments", params={"patient_id": str(uuid4())}).json()["total"], 0)
        self.assertEqual(self.client.get("/admin/appointments", params={"to_date": "9999-12-31"}).status_code, 200)
        for params in ({"from_date": "2026-11-01", "to_date": "2026-10-01"}, {"patient_id": "invalid"}, {"page": 0}, {"page_size": 101}):
            self.assertEqual(self.client.get("/admin/appointments", params=params).status_code, 422)

    def test_month_bounds_december_and_madrid_dst(self):
        service = AdminAppointmentQueryService(AppointmentRepository(self.db))
        _, end = service.month_bounds(datetime(2026, 12, 31, 12, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 12, 31, 23, tzinfo=timezone.utc))
        _, end = service.month_bounds(datetime(2026, 3, 1, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 3, 31, 22, tzinfo=timezone.utc))

    def test_existing_patch_cancels_optional_reason_and_audits_user_id(self):
        for row, body in [(self.rows[0], {"status": "cancelled"}), (self.rows[1], {"status": "cancelled", "reason": "Synthetic reason"})]:
            response = self.client.patch(f"/admin/appointments/{row.id}", json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "cancelled")
            log = self.db.scalar(select(AuditLog).where(AuditLog.entidad_id == row.id))
            self.assertEqual(log.patient_id, self.users[UserRole.PATIENT].id)
            history = self.db.scalar(select(AppointmentStatusHistory).where(AppointmentStatusHistory.appointment_id == row.id))
            self.assertEqual(history.reason, body.get("reason"))
            self.assertEqual(self.client.delete(f"/admin/appointments/{row.id}").status_code, 405)
        count = self.db.scalar(select(func.count()).select_from(AppointmentStatusHistory))
        self.client.patch(f"/admin/appointments/{self.rows[0].id}", json={"status": "cancelled"})
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AppointmentStatusHistory)), count)

    def test_create_and_admin_authorization(self):
        body = {"patient_id": str(self.users[UserRole.PATIENT].id), "professional_id": str(self.users[UserRole.PROFESSIONAL].id),
                "start_time": "2026-12-10T10:00:00Z", "end_time": "2026-12-10T11:00:00Z", "type": "in_person"}
        self.assertEqual(self.client.post("/admin/appointments", json=body).status_code, 201)
        self.assertEqual(self.client.post("/admin/appointments", json={**body, "patient_id": str(uuid4())}).status_code, 404)
        for role in (UserRole.PATIENT, UserRole.PROFESSIONAL):
            self.actor.role = role
            for path in ("/admin/appointments", "/admin/appointments/upcoming-month"):
                self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.client.post("/admin/appointments", json=body).status_code, 403)
            self.assertEqual(self.client.patch(f"/admin/appointments/{self.rows[0].id}", json={"status": "cancelled"}).status_code, 403)
        del app.dependency_overrides[get_current_user]
        self.assertEqual(self.client.get("/admin/appointments").status_code, 401)
