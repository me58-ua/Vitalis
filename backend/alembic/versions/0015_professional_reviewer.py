"""add professional reviewer

Revision ID: 0015_professional_reviewer
Revises: 0014_professional_approval
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0015_professional_reviewer"
down_revision: Union[str, Sequence[str], None] = "0014_professional_approval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "professional_profiles",
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_professional_profiles_reviewed_by_users",
        "professional_profiles",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_professional_profiles_reviewed_by_users",
        "professional_profiles",
        type_="foreignkey",
    )
    op.drop_column("professional_profiles", "reviewed_by")
