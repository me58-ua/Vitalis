import unittest
from datetime import date, datetime, timezone, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.main import app
from app.api.deps import get_audit_repository, get_current_user, get_user_repository
from app.models import AuditLog, AuditAction, User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository


class AdminReportingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        User.__table__.create(self.engine)
        AuditLog.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.actor = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
        self.timestamp = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        for role in UserRole:
            self.db.add(User(id=uuid4(), name="Synthetic", dni=role.value, username=role.value,
                             email=role.value + "@example.invalid", password_hash="unused",
                             role=role, tel="000", birth_date=date(1990, 1, 1), is_active=True))
        self.row = AuditLog(id=uuid4(), actor_id=self.actor.id, actor_role=UserRole.ADMIN,
                            accion=AuditAction.UPDATE, entidad="user_role", entidad_id=uuid4(),
                            fecha_hora=self.timestamp)
        self.other = AuditLog(id=uuid4(), actor_id=uuid4(), actor_role=UserRole.PROFESSIONAL,
                              accion=AuditAction.READ, entidad="=HYPERLINK(test)", fecha_hora=self.timestamp - timedelta(days=2))
        self.db.add_all([self.row, self.other])
        self.db.flush()
        overrides = app.dependency_overrides.copy()
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(overrides)))
        app.dependency_overrides[get_current_user] = lambda: self.actor
        app.dependency_overrides[get_audit_repository] = lambda: AuditRepository(self.db)
        app.dependency_overrides[get_user_repository] = lambda: UserRepository(self.db)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_list_filters_stable_pagination_and_no_writes(self):
        first = self.client.get("/admin/audit-logs", params={"page_size": 1}).json()
        second = self.client.get("/admin/audit-logs", params={"page_size": 1, "page": 2}).json()
        self.assertEqual(first["total"], 2)
        self.assertNotEqual(first["items"][0]["id"], second["items"][0]["id"])
        filters = {"actor_id": str(self.actor.id), "actor_role": "admin", "accion": "modificacion",
                   "entidad": "user_role", "entidad_id": str(self.row.entidad_id),
                   "from_date": "2026-10-29T13:00:00+01:00", "to_date": self.timestamp.isoformat()}
        result = self.client.get("/admin/audit-logs", params=filters)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.headers["cache-control"], "no-store")
        self.assertEqual(result.json()["total"], 1)
        self.assertIsNone(result.json()["items"][0]["patient_id"])
        self.assertEqual(self.client.get("/admin/audit-logs", params={"entidad": "not_present"}).json()["items"], [])
        self.assertTrue(result.json()["items"][0]["fecha_hora"].endswith("Z"))
        self.assertEqual(self.client.get("/admin/audit-logs", params={"patient_id": str(uuid4())}).json()["total"], 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AuditLog)), 2)

    def test_invalid_dates_enums_and_pagination(self):
        for params in ({"from_date": "2026-10-29"}, {"from_date": "2026-10-30T00:00:00Z", "to_date": "2026-10-29T00:00:00Z"},
                       {"page": 0}, {"page_size": 101}, {"actor_id": "bad"}, {"accion": "bad"},
                       {"actor_role": "bad"}, {"entidad": "x" * 81}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/admin/audit-logs", params=params).status_code, 422)

    def test_admin_only_and_no_mutation_routes(self):
        for role in (UserRole.PATIENT, UserRole.PROFESSIONAL):
            self.actor.role = role
            for path in ("/admin/audit-logs",):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.actor.role = UserRole.ADMIN
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(self.client, method)("/admin/audit-logs").status_code, 405)
        del app.dependency_overrides[get_current_user]
        self.assertEqual(self.client.get("/admin/audit-logs").status_code, 401)
        self.assertEqual(self.client.get("/admin/reports/export").status_code, 404)

    def test_same_timestamp_has_deterministic_order_and_inclusive_dates(self):
        tied = AuditLog(id=uuid4(), actor_id=self.actor.id, actor_role=UserRole.ADMIN,
                        accion=AuditAction.READ, entidad="test_tie", fecha_hora=self.timestamp)
        self.db.add(tied)
        self.db.flush()
        response = self.client.get("/admin/audit-logs", params={
            "from_date": self.timestamp.isoformat(), "to_date": self.timestamp.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)
        ids = [item["id"] for item in response.json()["items"]]
        self.assertEqual(ids, sorted([str(tied.id), str(self.row.id)], reverse=True))
