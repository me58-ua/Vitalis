"""Remove the unused patient body measurement timestamp."""

from alembic import op
import sqlalchemy as sa


revision = "0026_drop_body_measured_at"
down_revision = "0025_add_risk_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("patient_profiles", "body_measured_at")


def downgrade() -> None:
    op.add_column(
        "patient_profiles",
        sa.Column("body_measured_at", sa.DateTime(timezone=True), nullable=True),
    )
