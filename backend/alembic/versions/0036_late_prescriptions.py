"""Stage late prescriptions for administrative approval."""
from alembic import op
import sqlalchemy as sa

revision = "0036_late_prescriptions"
down_revision = "0035_expand_family_history"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "late_prescription_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("appointment_id", sa.Uuid(), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("draft", sa.JSON(none_as_null=True)),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("uq_late_prescription_pending", "late_prescription_requests", ["appointment_id"],
                    unique=True, postgresql_where=sa.text("approved_at IS NULL"))


def downgrade():
    op.drop_table("late_prescription_requests")
