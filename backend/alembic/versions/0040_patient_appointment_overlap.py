"""Prevent a patient from having overlapping non-cancelled appointments."""
from alembic import op

revision = "0040_patient_appointment_overlap"
down_revision = "0039_appointment_health_sharing"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE appointments ADD CONSTRAINT no_overlapping_patient_appointments
        EXCLUDE USING gist (patient_id WITH =, tstzrange(start_time, end_time) WITH &&)
        WHERE (status != 'cancelled')
    """)


def downgrade():
    op.execute("ALTER TABLE appointments DROP CONSTRAINT no_overlapping_patient_appointments")
