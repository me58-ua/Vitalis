"""Support automatic professional no-shows and system audit entries."""
from alembic import op

revision = "0041_video_professional_no_show"
down_revision = "0040_patient_appointment_overlap"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE appointment_status ADD VALUE 'noshow_professional'")
    op.alter_column("appointment_status_history", "changed_by", nullable=True)
    op.alter_column("audit_logs", "actor_id", nullable=True)
    op.alter_column("audit_logs", "actor_role", nullable=True)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM appointments WHERE status = 'noshow_professional')
               OR EXISTS (SELECT 1 FROM appointment_status_history
                          WHERE changed_by IS NULL OR old_status = 'noshow_professional'
                             OR new_status = 'noshow_professional')
               OR EXISTS (SELECT 1 FROM audit_logs WHERE actor_id IS NULL OR actor_role IS NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade while professional no-shows or system audit entries exist';
            END IF;
        END $$;
    """)
    op.alter_column("appointment_status_history", "changed_by", nullable=False)
    op.alter_column("audit_logs", "actor_id", nullable=False)
    op.alter_column("audit_logs", "actor_role", nullable=False)
    op.execute("ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT")
    constraints = {
        "no_overlapping_appointments": "professional_id",
        "no_overlapping_patient_appointments": "patient_id",
    }
    for name in constraints:
        op.drop_constraint(name, "appointments")
    op.execute("ALTER TYPE appointment_status RENAME TO appointment_status_previous")
    op.execute("CREATE TYPE appointment_status AS ENUM ('confirmed', 'cancelled', 'completed', 'no_show')")
    for table, column in (
        ("appointments", "status"),
        ("appointment_status_history", "old_status"),
        ("appointment_status_history", "new_status"),
    ):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE appointment_status USING {column}::text::appointment_status")
    op.execute("DROP TYPE appointment_status_previous")
    op.execute("ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'confirmed'")
    for name, owner in constraints.items():
        op.execute(f"""
            ALTER TABLE appointments ADD CONSTRAINT {name}
            EXCLUDE USING gist ({owner} WITH =, tstzrange(start_time, end_time) WITH &&)
            WHERE (status != 'cancelled')
        """)
