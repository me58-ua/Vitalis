"""Check the real enum migration in a rolled-back PostgreSQL schema."""
import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import engine


def check():
    path = Path.cwd() / "alembic/versions/0028_automatically_confirm_appointments.py"
    spec = importlib.util.spec_from_file_location("auto_confirm_migration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Migration module unavailable")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "vitalis_enum_check_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            connection.exec_driver_sql("CREATE TYPE appointment_status AS ENUM ('pending', 'confirmed', 'cancelled', 'completed', 'no_show')")
            connection.exec_driver_sql("""CREATE TABLE appointments (
                id integer PRIMARY KEY, professional_id uuid NOT NULL,
                start_time timestamptz NOT NULL, end_time timestamptz NOT NULL,
                status appointment_status NOT NULL DEFAULT 'pending',
                CONSTRAINT no_overlapping_appointments EXCLUDE USING gist
                (professional_id WITH =, tstzrange(start_time, end_time) WITH &&)
                WHERE (status != 'cancelled'))""")
            connection.exec_driver_sql("CREATE TABLE appointment_status_history (id integer PRIMARY KEY, old_status appointment_status, new_status appointment_status NOT NULL)")
            connection.exec_driver_sql("""INSERT INTO appointments VALUES
                (1, '00000000-0000-4000-8000-000000000001', '2026-11-05 09:00Z', '2026-11-05 09:30Z', 'pending'),
                (2, '00000000-0000-4000-8000-000000000001', '2026-11-05 10:00Z', '2026-11-05 10:30Z', 'cancelled')""")
            connection.exec_driver_sql("INSERT INTO appointment_status_history VALUES (1, 'pending', 'confirmed'), (2, 'confirmed', 'cancelled'), (3, NULL, 'pending')")
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            statuses = connection.exec_driver_sql("SELECT status::text FROM appointments ORDER BY id").scalars().all()
            assert statuses == ['confirmed', 'cancelled']
            history = connection.exec_driver_sql("SELECT old_status::text, new_status::text FROM appointment_status_history ORDER BY id").all()
            assert history == [('confirmed', 'confirmed'), ('confirmed', 'cancelled'), (None, 'confirmed')]
            labels = connection.execute(text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'appointment_status'::regtype ORDER BY enumsortorder")).scalars().all()
            assert labels == ['confirmed', 'cancelled', 'completed', 'no_show']
            connection.exec_driver_sql("INSERT INTO appointments (id, professional_id, start_time, end_time) VALUES (3, '00000000-0000-4000-8000-000000000001', '2026-11-05 10:00Z', '2026-11-05 10:30Z')")
            assert connection.exec_driver_sql("SELECT status::text FROM appointments WHERE id = 3").scalar_one() == 'confirmed'
            try:
                with connection.begin_nested():
                    connection.exec_driver_sql("INSERT INTO appointments VALUES (4, '00000000-0000-4000-8000-000000000001', '2026-11-05 09:15Z', '2026-11-05 09:45Z', 'confirmed')")
            except IntegrityError:
                pass
            else:
                raise AssertionError("Overlap constraint was not restored")
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            assert connection.exec_driver_sql("SELECT 'pending'::appointment_status::text").scalar_one() == 'pending'
            assert connection.exec_driver_sql("SELECT status::text FROM appointments WHERE id = 1").scalar_one() == 'confirmed'
        finally:
            transaction.rollback()
    print("PostgreSQL migration: enum, history, defaults, overlap constraint and downgrade verified; test schema rolled back.")


if __name__ == '__main__':
    check()
