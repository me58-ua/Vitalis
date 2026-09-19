"""add professional patient assignments

Revision ID: 0006_prof_patient_assignments
Revises: 0005_add_user_profiles
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_prof_patient_assignments"
down_revision: Union[str, Sequence[str], None] = "0005_add_user_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "professional_patient_assignments",
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["professional_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("professional_id", "patient_id"),
    )
    op.create_index(
        "ix_professional_patient_assignments_patient_id",
        "professional_patient_assignments",
        ["patient_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_professional_patient_assignments_patient_id",
        table_name="professional_patient_assignments",
    )
    op.drop_table("professional_patient_assignments")