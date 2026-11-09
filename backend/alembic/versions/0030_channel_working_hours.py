"""Separate weekly consultation and spontaneous-chat working hours."""
from alembic import op
import sqlalchemy as sa

revision = "0030_channel_working_hours"
down_revision = "0029_blocks_profile_review"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("professional_schedules", sa.Column("channel", sa.String(20), nullable=False, server_default="consultation"))
    op.create_check_constraint("valid_schedule_channel", "professional_schedules", "channel IN ('consultation', 'chat')")
    # Serialize schedule edits and bookings on the professional account. Legacy
    # rows stay consultations, without inventing chat availability or moving visits.
    op.execute("""
    CREATE FUNCTION vitalis_guard_weekly_schedule() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        PERFORM id FROM users WHERE id = OLD.professional_id FOR UPDATE;
        RETURN OLD;
      END IF;
      PERFORM id FROM users WHERE id = NEW.professional_id FOR UPDATE;
      IF NEW.is_active AND EXISTS (
        SELECT 1 FROM professional_schedules s WHERE s.professional_id=NEW.professional_id
          AND s.id != NEW.id AND s.is_active AND s.channel=NEW.channel
          AND s.day_of_week=NEW.day_of_week AND s.start_time < NEW.end_time AND s.end_time > NEW.start_time
      ) THEN
        RAISE EXCEPTION 'SCHEDULE_OVERLAP' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_weekly_schedule BEFORE INSERT OR UPDATE OR DELETE ON professional_schedules
      FOR EACH ROW EXECUTE FUNCTION vitalis_guard_weekly_schedule();
    """)
    op.execute("""
    CREATE FUNCTION vitalis_guard_booking_hours() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE local_start timestamp; local_end timestamp;
    BEGIN
      IF NEW.status::text = 'cancelled' THEN RETURN NEW; END IF;
      IF TG_OP='UPDATE' THEN
        IF NEW.professional_id=OLD.professional_id AND NEW.start_time=OLD.start_time
          AND NEW.end_time=OLD.end_time AND OLD.status::text != 'cancelled' THEN RETURN NEW; END IF;
      END IF;
      PERFORM id FROM users WHERE id=NEW.professional_id FOR UPDATE;
      local_start := NEW.start_time AT TIME ZONE 'Europe/Madrid';
      local_end := NEW.end_time AT TIME ZONE 'Europe/Madrid';
      IF local_start::date != local_end::date OR NOT EXISTS (
        SELECT 1 FROM professional_schedules s WHERE s.professional_id=NEW.professional_id
          AND s.channel='consultation' AND s.is_active
          AND s.day_of_week=EXTRACT(ISODOW FROM local_start)::int - 1
          AND s.start_time <= local_start::time AND s.end_time >= local_end::time
      ) THEN
        RAISE EXCEPTION 'OUTSIDE_WORKING_HOURS' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_booking_hours BEFORE INSERT OR UPDATE OF professional_id,start_time,end_time,status ON appointments
      FOR EACH ROW EXECUTE FUNCTION vitalis_guard_booking_hours();
    """)


def downgrade():
    op.execute("DROP TRIGGER guard_booking_hours ON appointments")
    op.execute("DROP FUNCTION vitalis_guard_booking_hours()")
    op.execute("DROP TRIGGER guard_weekly_schedule ON professional_schedules")
    op.execute("DROP FUNCTION vitalis_guard_weekly_schedule()")
    # Chat windows must never become bookable consultation windows on rollback.
    op.execute("DELETE FROM professional_schedules WHERE channel='chat'")
    op.drop_constraint("valid_schedule_channel", "professional_schedules", type_="check")
    op.drop_column("professional_schedules", "channel")
