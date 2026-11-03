"""Exercise real PostgreSQL constraints/API handlers in a rolled-back schema."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import MetaData, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.database import engine, get_db
from app.main import app
from app.models import User, PatientProfile, ProfessionalProfile, Appointment, AuditLog, AppointmentStatusHistory, Notification, UserRole
from app.scripts.seed_users import seed_users
from sqlalchemy.orm import sessionmaker


def check():
    overrides = app.dependency_overrides.copy()
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "vitalis_appointments_check_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            metadata = MetaData()
            for model in (User, PatientProfile, ProfessionalProfile, Appointment, AuditLog, AppointmentStatusHistory, Notification):
                model.__table__.to_metadata(metadata)
            metadata.create_all(connection, checkfirst=False)
            factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
            assert seed_users(factory, include_demo=False) == 3
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                users = {row.role: row for row in db.scalars(select(User))}
                actor = SimpleNamespace(id=users[UserRole.ADMIN].id, role=UserRole.ADMIN)
                app.dependency_overrides[get_db] = lambda: db
                app.dependency_overrides[get_current_user] = lambda: actor
                client = TestClient(app)
                try:
                    start = datetime.now(timezone.utc) + timedelta(hours=1)
                    body = {"patient_id": str(users[UserRole.PATIENT].id), "professional_id": str(users[UserRole.PROFESSIONAL].id),
                            "start_time": start.isoformat(), "end_time": (start + timedelta(minutes=30)).isoformat(), "type": "video"}
                    response = client.post("/admin/appointments", json=body)
                    assert response.status_code == 201, "Create failed"
                    appointment_id = response.json()["id"]
                    db.commit()
                    assert client.post("/admin/appointments", json=body).status_code == 409, "PostgreSQL overlap constraint missing"
                    response = client.patch(f"/admin/appointments/{appointment_id}", json={"status": "cancelled", "reason": "Synthetic cancellation"})
                    assert response.status_code == 200, "Cancellation failed"
                    db.commit()
                    log = db.scalar(select(AuditLog))
                    assert log.patient_id == users[UserRole.PATIENT].id
                    assert log.patient_id != db.scalar(select(PatientProfile.id))
                    assert db.scalar(select(AppointmentStatusHistory.reason)) == "Synthetic cancellation"
                    response = client.get("/admin/appointments", params={"patient_id": body["patient_id"]})
                    assert response.status_code == 200 and response.json()["total"] == 1
                    assert "room_id" not in response.json()["appointments"][0]
                    assert client.delete(f"/admin/appointments/{appointment_id}").status_code == 405
                    # Cancelled bookings release their original timeslot.
                    response = client.post("/admin/appointments", json=body)
                    assert response.status_code == 201
                    db.commit()
                    assert client.patch(f"/admin/appointments/{response.json()['id']}", json={"status": "cancelled"}).status_code == 200
                    db.commit()
                    print("PostgreSQL API handlers: create, overlap conflict, PATCH cancellation with/without reason, user-linked audit, filtered summaries and no DELETE verified.")
                finally:
                    client.close()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(overrides)
            transaction.rollback()
    print("All appointment test data and isolated schema rolled back; application records unchanged.")


if __name__ == "__main__":
    check()
