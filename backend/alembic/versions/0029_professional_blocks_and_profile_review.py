"""Professional unavailable intervals and reviewed profile change requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0029_blocks_profile_review"
down_revision = "0028_auto_confirm_appointments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "professional_time_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(250)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("end_time > start_time", name="valid_block_time_range"),
    )
    op.create_index("ix_professional_time_blocks_professional_id", "professional_time_blocks", ["professional_id"])
    for name, typ in (
        ("pending_changes", sa.JSON()), ("change_request_id", postgresql.UUID(as_uuid=True)),
        ("change_status", sa.String(20)), ("change_requested_at", sa.DateTime(timezone=True)),
        ("change_reviewed_at", sa.DateTime(timezone=True)), ("change_reviewed_by", postgresql.UUID(as_uuid=True)),
        ("change_rejection_reason", sa.Text()),
    ):
        op.add_column("professional_profiles", sa.Column(name, typ, nullable=True))
    op.create_foreign_key("fk_profile_change_reviewer", "professional_profiles", "users", ["change_reviewed_by"], ["id"], ondelete="SET NULL")
    # Both directions serialize on the same account row. This protects all booking
    # entry points, including administrative reschedules and concurrent requests.
    op.execute("""
    CREATE FUNCTION vitalis_guard_unavailable_time() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM id FROM users WHERE id = NEW.professional_id FOR UPDATE;
      IF TG_TABLE_NAME = 'appointments' THEN
        IF NEW.status::text != 'cancelled' AND EXISTS (
          SELECT 1 FROM professional_time_blocks b WHERE b.professional_id = NEW.professional_id
            AND b.start_time < NEW.end_time AND b.end_time > NEW.start_time
        ) THEN
          RAISE EXCEPTION 'PROFESSIONAL_TIME_BLOCKED' USING ERRCODE = '23514';
        END IF;
      ELSE
        IF EXISTS (
          SELECT 1 FROM appointments a WHERE a.professional_id = NEW.professional_id
            AND a.status::text != 'cancelled'
            AND a.start_time < NEW.end_time AND a.end_time > NEW.start_time
        ) OR EXISTS (
          SELECT 1 FROM professional_time_blocks b WHERE b.professional_id = NEW.professional_id
            AND b.id != NEW.id AND b.start_time < NEW.end_time AND b.end_time > NEW.start_time
        ) THEN
          RAISE EXCEPTION 'TIME_BLOCK_CONFLICT' USING ERRCODE = '23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    """)
    op.execute("CREATE TRIGGER guard_appointment_unavailable BEFORE INSERT OR UPDATE OF professional_id, start_time, end_time, status ON appointments FOR EACH ROW EXECUTE FUNCTION vitalis_guard_unavailable_time()")
    op.execute("CREATE TRIGGER guard_time_block BEFORE INSERT OR UPDATE ON professional_time_blocks FOR EACH ROW EXECUTE FUNCTION vitalis_guard_unavailable_time()")


def downgrade():
    op.execute("DROP TRIGGER guard_appointment_unavailable ON appointments")
    op.execute("DROP TRIGGER guard_time_block ON professional_time_blocks")
    op.execute("DROP FUNCTION vitalis_guard_unavailable_time()")
    op.drop_constraint("fk_profile_change_reviewer", "professional_profiles", type_="foreignkey")
    for name in ("pending_changes", "change_request_id", "change_status", "change_requested_at", "change_reviewed_at", "change_reviewed_by", "change_rejection_reason"):
        op.drop_column("professional_profiles", name)
    op.drop_index("ix_professional_time_blocks_professional_id", table_name="professional_time_blocks")
    op.drop_table("professional_time_blocks")
