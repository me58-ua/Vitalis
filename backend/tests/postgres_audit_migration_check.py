"""Explicit PostgreSQL check; only creates a rolled-back, isolated test schema.

Run in the rebuilt API container before applying the migration to public tables.
It never reads application/patient rows. Not part of SQLite unittest discovery.
"""
import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from app.database import engine


def check():
    path = Path("alembic/versions/0027_audit_patient_user.py")
    spec = importlib.util.spec_from_file_location("audit_migration_under_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "vitalis_migration_check_" + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            connection.exec_driver_sql("CREATE TABLE users (id uuid PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TABLE patient_profiles (id uuid PRIMARY KEY, user_id uuid UNIQUE REFERENCES users(id))")
            connection.exec_driver_sql("CREATE TABLE audit_logs (id uuid PRIMARY KEY, patient_id uuid REFERENCES patient_profiles(id) ON DELETE SET NULL, payload text)")
            user, profile, row, null_row = [uuid4() for _ in range(4)]
            connection.execute(text("INSERT INTO users VALUES (:id)"), {"id": user})
            connection.execute(text("INSERT INTO patient_profiles VALUES (:id,:user)"), {"id": profile, "user": user})
            connection.execute(text("INSERT INTO audit_logs VALUES (:id,:patient,'unchanged')"), {"id": row, "patient": profile})
            connection.execute(text("INSERT INTO audit_logs VALUES (:id,NULL,'null-link')"), {"id": null_row})
            migration.op = Operations(MigrationContext.configure(connection))
            for direction, expected, target in [(migration.upgrade, user, "users"), (migration.downgrade, profile, "patient_profiles"), (migration.upgrade, user, "users")]:
                direction()
                result = connection.execute(text("SELECT patient_id, payload FROM audit_logs WHERE id=:id"), {"id": row}).one()
                assert result == (expected, "unchanged")
                assert connection.scalar(text("SELECT count(*) FROM audit_logs")) == 2
                assert connection.scalar(text("SELECT patient_id FROM audit_logs WHERE id=:id"), {"id": null_row}) is None
                assert inspect(connection).get_foreign_keys("audit_logs")[0]["referred_table"] == target
            print("PostgreSQL migration: upgrade/downgrade/upgrade preserve rows, null links and resource data; FK targets verified.")
        finally:
            transaction.rollback()
    print("Isolated migration test schema rolled back; application data unchanged.")


if __name__ == "__main__":
    check()
