"""Automatically confirm bookings and remove the pending appointment state.

The conversion includes status history and rebuilds the overlap constraint.
Professional approval and email delivery have their own, unchanged enums.
"""
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028_auto_confirm_appointments"
down_revision = "0027_audit_patient_user"
branch_labels = None
depends_on = None


def _replace_type(values, default, convert_pending=False):
    op.execute("ALTER TABLE appointments DROP CONSTRAINT no_overlapping_appointments")
    op.execute("ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE appointment_status RENAME TO appointment_status_previous")
    postgresql.ENUM(*values, name="appointment_status").create(op.get_bind(), checkfirst=False)
    for table, column in (
        ("appointments", "status"),
        ("appointment_status_history", "old_status"),
        ("appointment_status_history", "new_status"),
    ):
        source = f"{column}::text"
        if convert_pending:
            source = f"CASE WHEN {column}::text = 'pending' THEN 'confirmed' ELSE {column}::text END"
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE appointment_status USING ({source})::appointment_status")
    op.execute("DROP TYPE appointment_status_previous")
    op.execute(f"ALTER TABLE appointments ALTER COLUMN status SET DEFAULT '{default}'::appointment_status")
    op.execute("""
        ALTER TABLE appointments ADD CONSTRAINT no_overlapping_appointments
        EXCLUDE USING gist (professional_id WITH =, tstzrange(start_time, end_time) WITH &&)
        WHERE (status != 'cancelled')
    """)


def upgrade():
    _replace_type(("confirmed", "cancelled", "completed", "no_show"), "confirmed", convert_pending=True)


def downgrade():
    # Restore the old enum/default without guessing which confirmed bookings
    # used to be pending before this migration.
    _replace_type(("pending", "confirmed", "cancelled", "completed", "no_show"), "pending")
