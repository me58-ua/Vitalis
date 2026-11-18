"""Separate in-person and video working hours."""
from alembic import op

revision = "0038_modality_working_hours"
down_revision = "0037_appointment_follow_up"
branch_labels = None
depends_on = None


def replace_booking_guard(channel_rule, *, separate_modalities):
    # Existing bookings can still be cancelled or have their status changed after
    # their original schedule is edited. A modality change needs revalidation.
    same_type = "AND NEW.type=OLD.type" if separate_modalities else ""
    update_type = ",type" if separate_modalities else ""
    op.execute("DROP TRIGGER guard_booking_hours ON appointments")
    op.execute(f"""
    CREATE OR REPLACE FUNCTION vitalis_guard_booking_hours() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE local_start timestamp; local_end timestamp;
    BEGIN
      IF NEW.status::text = 'cancelled' THEN RETURN NEW; END IF;
      IF TG_OP='UPDATE' THEN
        IF NEW.professional_id=OLD.professional_id AND NEW.start_time=OLD.start_time
          AND NEW.end_time=OLD.end_time {same_type}
          AND OLD.status::text != 'cancelled' THEN RETURN NEW; END IF;
      END IF;
      PERFORM id FROM users WHERE id=NEW.professional_id FOR UPDATE;
      local_start := NEW.start_time AT TIME ZONE 'Europe/Madrid';
      local_end := NEW.end_time AT TIME ZONE 'Europe/Madrid';
      IF local_start::date != local_end::date OR NOT EXISTS (
        SELECT 1 FROM professional_schedules s WHERE s.professional_id=NEW.professional_id
          AND {channel_rule} AND s.is_active
          AND s.day_of_week=EXTRACT(ISODOW FROM local_start)::int - 1
          AND s.start_time <= local_start::time AND s.end_time >= local_end::time
      ) THEN
        RAISE EXCEPTION 'OUTSIDE_WORKING_HOURS' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_booking_hours BEFORE INSERT OR UPDATE OF professional_id,start_time,end_time,status{update_type}
      ON appointments FOR EACH ROW EXECUTE FUNCTION vitalis_guard_booking_hours();
    """)


def upgrade():
    op.drop_constraint("valid_schedule_channel", "professional_schedules", type_="check")
    op.execute("UPDATE professional_schedules SET channel='in_person' WHERE channel='consultation'")
    # Preserve the modalities previously offered by each existing shared block.
    op.execute("""
        INSERT INTO professional_schedules
            (professional_id, day_of_week, channel, start_time, end_time, slot_duration_min, is_active, created_at)
        SELECT s.professional_id, s.day_of_week, 'video', s.start_time, s.end_time,
               s.slot_duration_min, s.is_active, s.created_at
        FROM professional_schedules s
        JOIN professional_profiles p ON p.user_id=s.professional_id AND p.telehealth_enabled
        WHERE s.channel='in_person'
    """)
    op.alter_column("professional_schedules", "channel", server_default="in_person")
    op.create_check_constraint("valid_schedule_channel", "professional_schedules", "channel IN ('in_person', 'video', 'chat')")
    replace_booking_guard("s.channel=NEW.type::text", separate_modalities=True)


def downgrade():
    op.drop_constraint("valid_schedule_channel", "professional_schedules", type_="check")
    op.execute("""
        DELETE FROM professional_schedules v
        USING professional_schedules p
        WHERE v.channel='video' AND p.channel='in_person'
          AND v.professional_id=p.professional_id AND v.day_of_week=p.day_of_week
          AND v.start_time=p.start_time AND v.end_time=p.end_time
          AND v.slot_duration_min=p.slot_duration_min AND v.is_active=p.is_active
    """)
    # The existing overlap guard rejects a downgrade if different active
    # intervals cannot be represented by the old shared channel.
    op.execute("UPDATE professional_schedules SET channel='consultation' WHERE channel IN ('video', 'in_person')")
    op.alter_column("professional_schedules", "channel", server_default="consultation")
    op.create_check_constraint("valid_schedule_channel", "professional_schedules", "channel IN ('consultation', 'chat')")
    replace_booking_guard("s.channel='consultation'", separate_modalities=False)
