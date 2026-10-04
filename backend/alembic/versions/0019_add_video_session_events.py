"""add video session events and textual room ids

Revision ID: 0019_add_video_session_events
Revises: 0018_add_audit_logs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0019_add_video_session_events"
down_revision: Union[str, Sequence[str], None] = "0018_add_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "appointments",
        "room_id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(length=128),
        postgresql_using="room_id::text",
    )
    op.create_table(
        "video_session_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_video_session_events_appointment", "video_session_events", ["appointment_id"])
    op.create_index("idx_video_session_events_user", "video_session_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_video_session_events_user", table_name="video_session_events")
    op.drop_index("idx_video_session_events_appointment", table_name="video_session_events")
    op.drop_table("video_session_events")
    op.alter_column(
        "appointments",
        "room_id",
        existing_type=sa.String(length=128),
        type_=postgresql.UUID(as_uuid=True),
        postgresql_using="room_id::uuid",
    )
