"""Verify migration and bidirectional booking/block constraints in a rolled-back schema."""
import importlib.util
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models import ProfessionalProfile, ProfessionalApprovalStatus, UserRole
from app.repositories.profile_repository import ProfileRepository
from app.services.profile_change_service import ProfileChangeService, ProfileChangeConflict
from app.schemas.professional_management import ProfileChangeDecision
from app.schemas.profiles import ProfessionalProfileUpdate


def check():
    spec = importlib.util.spec_from_file_location("management_migration", Path.cwd() / "alembic/versions/0029_professional_blocks_and_profile_review.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "vitalis_management_check_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            connection.exec_driver_sql("CREATE TABLE users (id uuid PRIMARY KEY)")
            ProfessionalProfile.__table__.create(connection)
            for column in ('pending_changes', 'change_request_id', 'change_status', 'change_requested_at', 'change_reviewed_at', 'change_reviewed_by', 'change_rejection_reason'):
                connection.exec_driver_sql(f'ALTER TABLE professional_profiles DROP COLUMN {column}')
            connection.exec_driver_sql("CREATE TABLE appointments (id uuid PRIMARY KEY, professional_id uuid REFERENCES users(id), start_time timestamptz NOT NULL, end_time timestamptz NOT NULL, status text NOT NULL)")
            with Operations.context(MigrationContext.configure(connection)): migration.upgrade()
            professional, other, block = uuid4(), uuid4(), uuid4()
            connection.exec_driver_sql("INSERT INTO users VALUES (%s), (%s)", (professional, other))
            def booking(start, end, status='confirmed', owner=professional):
                connection.exec_driver_sql("INSERT INTO appointments VALUES (%s,%s,%s,%s,%s)", (uuid4(), owner, start, end, status))
            def blocked(start, end, owner=professional):
                connection.exec_driver_sql("INSERT INTO professional_time_blocks (id,professional_id,start_time,end_time) VALUES (%s,%s,%s,%s)", (uuid4(), owner, start, end))
            def conflict(operation):
                try:
                    with connection.begin_nested(): operation()
                except IntegrityError: return
                raise AssertionError('Expected overlap/interval conflict')
            connection.exec_driver_sql("INSERT INTO professional_time_blocks (id,professional_id,start_time,end_time) VALUES (%s,%s,'2030-07-01Z','2030-07-08Z')", (block, professional))
            conflict(lambda: booking('2030-07-02 09:00Z', '2030-07-02 10:00Z'))
            booking('2030-07-02 09:00Z', '2030-07-02 10:00Z', 'cancelled')
            booking('2030-07-02 09:00Z', '2030-07-02 10:00Z', owner=other)
            booking('2030-07-08Z', '2030-07-08 01:00Z')
            booking('2030-06-30 23:00Z', '2030-07-01Z')
            conflict(lambda: blocked('2030-07-03Z', '2030-07-04Z'))
            conflict(lambda: blocked('2030-07-08 00:30Z', '2030-07-08 02:00Z'))
            conflict(lambda: blocked('2030-08-01Z', '2030-07-31Z'))
            conflict(lambda: connection.exec_driver_sql("UPDATE appointments SET status='confirmed' WHERE status='cancelled'"))
            conflict(lambda: connection.exec_driver_sql("UPDATE appointments SET start_time='2030-07-03 09:00Z',end_time='2030-07-03 10:00Z' WHERE start_time='2030-07-08Z'"))
            connection.exec_driver_sql("DELETE FROM professional_time_blocks WHERE id=%s", (block,))
            booking('2030-07-03 09:00Z', '2030-07-03 10:00Z')
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                profile = ProfessionalProfile(user_id=professional, specialty='Medicina general', license_number='CHECK-COL', approval_status=ProfessionalApprovalStatus.APPROVED)
                db.add(profile)
                db.flush()
                service = ProfileChangeService(ProfileRepository(db))
                actor = SimpleNamespace(id=professional, role=UserRole.PROFESSIONAL)
                admin = SimpleNamespace(id=other, role=UserRole.ADMIN)
                service.submit(actor, ProfessionalProfileUpdate(specialty='Cardiología'))
                assert profile.specialty == 'Medicina general' and profile.change_status == 'pending'
                decision = ProfileChangeDecision(request_id=profile.change_request_id, reason='Falta acreditación')
                service.decide(professional, admin, decision, False)
                assert profile.specialty == 'Medicina general' and profile.change_status == 'rejected'
                service.submit(actor, ProfessionalProfileUpdate(specialty='Neurología'))
                try:
                    service.decide(professional, admin, decision, True)
                except ProfileChangeConflict:
                    pass
                else:
                    raise AssertionError('A stale request was approved')
                service.decide(professional, admin, ProfileChangeDecision(request_id=profile.change_request_id), True)
                db.expire_all()
                assert profile.specialty == 'Neurología' and profile.change_status == 'approved'
                assert profile.pending_changes is None and profile.change_reviewed_by == other
                db.commit()
            with Operations.context(MigrationContext.configure(connection)): migration.downgrade()
            assert connection.exec_driver_sql("SELECT to_regclass('professional_time_blocks')").scalar() is None
        finally:
            transaction.rollback()
    print('PostgreSQL: upgrade/downgrade, vacation overlap, boundaries, other owner, cancelled restoration, rescheduling and persistent profile submission/rejection/resubmission/stale protection/approval verified; schema rolled back.')


if __name__ == '__main__':
    check()
