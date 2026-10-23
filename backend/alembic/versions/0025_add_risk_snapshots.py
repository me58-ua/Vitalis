"""Persist successful risk evaluations for history and trends.

Revision ID: 0025_add_risk_snapshots
Revises: 0024_add_onboarding_state
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0025_add_risk_snapshots"
down_revision: Union[str, Sequence[str], None] = "0024_add_onboarding_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(40), nullable=False),
        sa.Column("metric_value", sa.Numeric(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("alert_level", sa.String(30), nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_risk_snapshots_patient_id", "risk_snapshots", ["patient_id"])
    op.create_index(
        "ix_risk_snapshots_patient_model_computed",
        "risk_snapshots", ["patient_id", "model", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_snapshots_patient_model_computed", table_name="risk_snapshots")
    op.drop_index("ix_risk_snapshots_patient_id", table_name="risk_snapshots")
    op.drop_table("risk_snapshots")
