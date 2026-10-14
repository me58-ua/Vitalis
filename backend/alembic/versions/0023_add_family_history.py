"""Add structured family history entries.

Revision ID: 0023_add_family_history
Revises: 0022_issue_26a_profile_alcohol
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0023_add_family_history"
down_revision: Union[str, Sequence[str], None] = "0022_issue_26a_profile_alcohol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_history_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship", sa.String(20), nullable=False),
        sa.Column("condition_category", sa.String(30), nullable=False),
        sa.Column("detail", sa.String(150), nullable=True),
        sa.Column("age_at_diagnosis", sa.Integer(), nullable=True),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "relationship IN ('madre', 'padre', 'hermano', 'hijo', 'abuelo', 'tio', 'otro')",
            name="ck_family_relationship_values",
        ),
        sa.CheckConstraint(
            "condition_category IN ('diabetes', 'cancer', 'cardiovascular', 'huntington', 'otro')",
            name="ck_family_condition_values",
        ),
        sa.CheckConstraint(
            "age_at_diagnosis IS NULL OR age_at_diagnosis BETWEEN 0 AND 120",
            name="ck_family_history_age_range",
        ),
    )
    op.create_index("ix_family_history_entries_patient_id", "family_history_entries", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_family_history_entries_patient_id", table_name="family_history_entries")
    op.drop_table("family_history_entries")
