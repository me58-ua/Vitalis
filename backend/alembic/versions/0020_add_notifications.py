"""add shared email and in-app notifications

Revision ID: 0020_add_notifications
Revises: 0019_add_video_session_events
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0020_add_notifications"
down_revision: Union[str, Sequence[str], None] = "0019_add_video_session_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    email_status = postgresql.ENUM(
        "pendiente", "enviada", "fallida", "no_aplica",
        name="notification_email_status",
    )
    email_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity", sa.String(length=80), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("email_status", email_status, server_default="no_aplica", nullable=False),
        sa.Column("email_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipient_id", "type", "entity_id", "scheduled_for",
            name="uq_notifications_recipient_type_entity_schedule",
        ),
    )
    op.create_index("idx_notifications_recipient_created", "notifications", ["recipient_id", "created_at"])
    op.create_index("idx_notifications_email_due", "notifications", ["email_status", "scheduled_for"])


def downgrade() -> None:
    op.drop_index("idx_notifications_email_due", table_name="notifications")
    op.drop_index("idx_notifications_recipient_created", table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notification_email_status").drop(op.get_bind(), checkfirst=True)
