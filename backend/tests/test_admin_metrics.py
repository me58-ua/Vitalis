import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import User, UserRole, Appointment, AppointmentStatus, AppointmentType
from app.repositories.user_repository import UserRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.services.admin_metrics_service import AdminMetricsService


class AdminMetricsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        metadata = MetaData()
        for model in (User, Appointment):
            table = model.__table__.to_metadata(metadata)
            for constraint in list(table.constraints):
                if isinstance(constraint, ExcludeConstraint):
                    table.constraints.remove(constraint)
        metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)
        self.service = AdminMetricsService(UserRepository(self.db), AppointmentRepository(self.db))
        self.now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        self.actor = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
        previous = app.dependency_overrides.copy()
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.actor
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def user(self, role, when):
        identity = uuid4()
        value = User(id=identity, role=role, name="Synthetic", dni=str(identity), username=str(identity),
                     email=str(identity) + "@example.invalid", password_hash="test-only", tel="000",
                     birth_date=date(1990, 1, 1), created_at=datetime.fromisoformat(when))
        self.db.add(value)
        return value

    def test_counts_calendar_boundaries_and_growth_include_cancelled(self):
        patient = self.user(UserRole.PATIENT, "2026-09-01T12:00:00+00:00")
        self.user(UserRole.PATIENT, "2026-09-30T21:59:00+00:00")
        self.user(UserRole.PATIENT, "2026-09-30T22:00:00+00:00")  # October in Madrid.
        professional = self.user(UserRole.PROFESSIONAL, "2026-10-05T12:00:00+00:00")
        self.user(UserRole.ADMIN, "2026-01-01T12:00:00+00:00")
        self.db.flush()
        for when, status in [("2026-09-01T12:00:00+00:00", AppointmentStatus.PENDING),
                             ("2026-09-30T21:59:00+00:00", AppointmentStatus.CONFIRMED),
                             ("2026-09-30T22:00:00+00:00", AppointmentStatus.PENDING),
                             ("2026-10-10T12:00:00+00:00", AppointmentStatus.COMPLETED),
                             ("2026-10-20T12:00:00+00:00", AppointmentStatus.CANCELLED),
                             ("2026-10-31T23:00:00+00:00", AppointmentStatus.CONFIRMED)]:
            start = datetime.fromisoformat(when)
            self.db.add(Appointment(patient_id=patient.id, professional_id=professional.id, start_time=start,
                                    end_time=start + timedelta(minutes=30), status=status, type=AppointmentType.VIDEO))
        self.db.flush()
        result = self.service.monthly(6, self.now)
        self.assertEqual(result.users.total, 5)
        self.assertEqual(result.users.change_percent, 0)
        self.assertEqual(result.patients.total, 3)
        self.assertEqual(result.patients.change_percent, -50)
        self.assertIsNone(result.professionals.change_percent)
        self.assertEqual(result.appointments.total, 3)
        self.assertEqual(result.appointments.change_percent, 50)
        self.assertEqual([item.appointments for item in result.series][-2:], [2, 3])
        self.assertEqual(result.series[-1].month, "2026-10")
        self.assertEqual(result.month_end, datetime(2026, 10, 31, 23, tzinfo=timezone.utc))
        self.assertEqual(result.month_start_date, date(2026, 10, 1))
        self.assertEqual(result.month_end_date, date(2026, 10, 31))

    def test_empty_zero_base_and_year_dst_boundaries(self):
        result = self.service.monthly(6, datetime(2027, 1, 15, tzinfo=timezone.utc))
        self.assertEqual(len(result.series), 6)
        self.assertEqual(result.series[-2].month, "2026-12")
        self.assertEqual(result.users.total, 0)
        self.assertEqual(result.users.change_percent, 0)
        self.assertTrue(all(item.appointments == 0 for item in result.series))
        self.assertIsNone(self.service.metric(2, [0, 2]).change_percent)
        self.assertEqual(self.service.metric(0, [4, 0]).change_percent, -100)
        self.assertEqual(self.service.metric(3, [2, 3]).change_percent, 50)
        march = self.service.monthly(2, datetime(2026, 3, 15, tzinfo=timezone.utc))
        self.assertEqual(march.month_end, datetime(2026, 3, 31, 22, tzinfo=timezone.utc))

    def test_endpoint_validation_and_admin_only(self):
        with patch('app.services.admin_metrics_service.datetime', wraps=datetime) as clock:
            clock.now.return_value = self.now
            response = self.client.get('/admin/metrics/monthly', params={'months': 6})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(len(response.json()['series']), 6)
        for months in (0, 1, 25, 'bad'):
            self.assertEqual(self.client.get('/admin/metrics/monthly', params={'months': months}).status_code, 422)
        for role in (UserRole.PATIENT, UserRole.PROFESSIONAL):
            self.actor.role = role
            self.assertEqual(self.client.get('/admin/metrics/monthly').status_code, 403)
        del app.dependency_overrides[get_current_user]
        self.assertEqual(self.client.get('/admin/metrics/monthly').status_code, 401)
