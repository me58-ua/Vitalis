"""add appointments, schedules, status history, and chat messages

Revision ID: 0009_add_appointments_and_chat
Revises: 0008_add_dni_to_users
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009_add_appointments_and_chat"
down_revision: Union[str, Sequence[str], None] = "0008_add_dni_to_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


appointment_type = postgresql.ENUM("video", "in_person", name="appointment_type", create_type=False)
appointment_status = postgresql.ENUM(
    "pending", "confirmed", "cancelled", "completed", "no_show",
    name="appointment_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    appointment_type.create(bind, checkfirst=True)
    appointment_status.create(bind, checkfirst=True)

    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", appointment_status, server_default="pending", nullable=False),
        sa.Column("type", appointment_type, server_default="video", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("end_time > start_time", name="valid_time_range"),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id"),
    )
    op.create_index("idx_appointments_professional_time", "appointments", ["professional_id", "start_time"])
    op.create_index("idx_appointments_patient", "appointments", ["patient_id"])
    op.execute(
        sa.text(
            """
            ALTER TABLE appointments
            ADD CONSTRAINT no_overlapping_appointments
            EXCLUDE USING gist (
                professional_id WITH =,
                tstzrange(start_time, end_time) WITH &&
            )
            WHERE (status != 'cancelled')
            """
        )
    )

    op.create_table(
        "professional_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("slot_duration_min", sa.SmallInteger(), server_default="30", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="valid_day_of_week"),
        sa.CheckConstraint("end_time > start_time", name="valid_schedule_range"),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_schedules_professional", "professional_schedules", ["professional_id", "day_of_week"])

    op.create_table(
        "appointment_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_status", appointment_status, nullable=True),
        sa.Column("new_status", appointment_status, nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_status_history_appointment", "appointment_status_history", ["appointment_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_messages_appointment", "chat_messages", ["appointment_id", "sent_at"])


def downgrade() -> None:
    op.drop_index("idx_chat_messages_appointment", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("idx_status_history_appointment", table_name="appointment_status_history")
    op.drop_table("appointment_status_history")
    op.drop_index("idx_schedules_professional", table_name="professional_schedules")
    op.drop_table("professional_schedules")
    op.execute(
        sa.text(
            "ALTER TABLE appointments DROP CONSTRAINT no_overlapping_appointments"
        )
    )
    op.drop_index("idx_appointments_patient", table_name="appointments")
    op.drop_index("idx_appointments_professional_time", table_name="appointments")
    op.drop_table("appointments")
    appointment_status.drop(op.get_bind(), checkfirst=True)
    appointment_type.drop(op.get_bind(), checkfirst=True)