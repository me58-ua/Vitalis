"""Synthetic dashboard/appointment contract tests; never use the configured database."""
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import (User, UserRole, PatientProfile, ProfessionalPatient, Appointment, AppointmentStatus,
                        AppointmentType, AppointmentStatusHistory, AuditLog, Notification, Allergy, ChronicCondition)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.services.professional_dashboard_service import ProfessionalDashboardService
from app.schemas.professional_dashboard import ProfessionalAppointmentsQuery


class ProfessionalDashboardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        metadata = MetaData()
        for model in (User, PatientProfile, ProfessionalPatient, Appointment, AppointmentStatusHistory, AuditLog, Notification, Allergy, ChronicCondition):
            table = model.__table__.to_metadata(metadata)
            for constraint in list(table.constraints):
                if isinstance(constraint, ExcludeConstraint):
                    table.constraints.remove(constraint)
        metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.professional = self.user("pro", UserRole.PROFESSIONAL)
        self.other = self.user("other", UserRole.PROFESSIONAL)
        self.patient = self.user("patient", UserRole.PATIENT)
        self.admin = self.user("admin", UserRole.ADMIN)
        self.db.add(PatientProfile(user_id=self.patient.id))
        self.db.add(ProfessionalPatient(professional_id=self.professional.id, patient_id=self.patient.id))
        self.db.flush()
        self.repository = AppointmentRepository(self.db)
        self.now = datetime(2026, 10, 28, 10, tzinfo=timezone.utc)
        self.service = ProfessionalDashboardService(self.repository, ProfessionalRepository(self.db), now=lambda: self.now)
        self.actor = self.professional
        previous = app.dependency_overrides.copy()
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.actor
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def user(self, tag, role):
        user = User(name=f"Synthetic {tag}", dni=f"TEST-{tag}", username=tag, email=f"{tag}@example.invalid",
                    password_hash="test-only", tel="000000000", birth_date=date(1990, 1, 1), role=role, is_active=True)
        self.db.add(user)
        self.db.flush()
        return user

    def appointment(self, start, status=AppointmentStatus.PENDING, professional=None):
        item = Appointment(patient_id=self.patient.id, professional_id=(professional or self.professional).id,
                           start_time=start, end_time=start + timedelta(minutes=30), status=status,
                           type=AppointmentType.VIDEO, appointment_reason="Original appointment motive")
        self.db.add(item)
        self.db.flush()
        return item

    def test_counts_include_seven_days_zeroes_and_only_own_non_cancelled_appointments(self):
        for index, status in enumerate((AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED,
                                        AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW, AppointmentStatus.CANCELLED)):
            self.appointment(self.now + timedelta(hours=index), status)
        self.appointment(self.now - timedelta(days=1))
        self.appointment(self.now + timedelta(days=4))  # Sunday is included.
        self.appointment(self.now, professional=self.other)
        result = self.service.dashboard(self.professional.id)
        self.assertEqual(result.appointments_today, 4)
        self.assertEqual(result.scheduled_today, 2)
        self.assertEqual(result.completed_today, 1)
        self.assertEqual(result.appointments_yesterday, 1)
        self.assertEqual(result.assigned_patients, 1)
        self.assertEqual([day.count for day in result.weekly_distribution], [0, 1, 4, 0, 0, 0, 1])
        self.assertEqual(result.week_start, date(2026, 10, 26))
        self.assertEqual(result.week_end, date(2026, 11, 1))

    def test_upcoming_includes_ongoing_and_pagination_does_not_leak_other_professionals(self):
        ongoing = self.appointment(self.now - timedelta(minutes=15))
        future = self.appointment(self.now + timedelta(hours=1), AppointmentStatus.CONFIRMED)
        self.appointment(self.now + timedelta(hours=2), AppointmentStatus.CANCELLED)
        self.appointment(self.now + timedelta(hours=3), AppointmentStatus.COMPLETED)
        self.appointment(self.now, professional=self.other)
        first = self.service.list_appointments(self.professional.id, ProfessionalAppointmentsQuery(page_size=1))
        second = self.service.list_appointments(self.professional.id, ProfessionalAppointmentsQuery(page_size=1, page=2))
        self.assertEqual(first.total, 2)
        self.assertEqual(first.appointments[0].id, ongoing.id)
        self.assertEqual(second.appointments[0].id, future.id)
        self.assertEqual(first.appointments[0].patient_name, self.patient.name)

    def test_madrid_day_bounds_include_both_dst_changes(self):
        for day, hours in ((date(2026, 3, 29), 23), (date(2026, 10, 25), 25)):
            duration = self.service.midnight(day + timedelta(days=1)) - self.service.midnight(day)
            self.assertEqual(duration, timedelta(hours=hours))

    def test_admin_cancellation_keeps_motive_and_returns_cancellation_reason(self):
        appointment = self.appointment(self.now + timedelta(days=5))
        self.actor = self.admin
        response = self.client.patch(f"/admin/appointments/{appointment.id}", json={
            "status": "cancelled", "cancellation_reason": "Cancellation only"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["appointment_reason"], "Original appointment motive")
        self.assertEqual(response.json()["cancellation_reason"], "Cancellation only")
        self.assertEqual(appointment.reason, "Original appointment motive")
        self.actor = self.professional
        result = self.client.get("/professionals/me/appointments", params={"upcoming_only": False})
        self.assertEqual(result.json()["appointments"][0]["cancellation_reason"], "Cancellation only")

    def test_professional_cancellation_and_legacy_payload_keep_motive(self):
        appointment = self.appointment(self.now + timedelta(days=5))
        response = self.client.post(f"/professionals/{self.professional.id}/appointments/{appointment.id}/cancel",
                                    json={"reason": "Legacy cancellation"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["appointment_reason"], "Original appointment motive")
        self.assertEqual(response.json()["cancellation_reason"], "Legacy cancellation")

    def test_dashboard_role_and_query_validation(self):
        self.assertEqual(self.client.get("/professionals/me/dashboard").status_code, 200)
        for actor in (self.patient, self.admin):
            self.actor = actor
            self.assertEqual(self.client.get("/professionals/me/dashboard").status_code, 403)
        self.actor = self.professional
        for params in ({"page": 0}, {"page_size": 101}, {"status": "confirmada"},
                       {"from_date": "2026-11-01", "to_date": "2026-10-01"}):
            self.assertEqual(self.client.get("/professionals/me/appointments", params=params).status_code, 422)


if __name__ == "__main__":
    unittest.main()
