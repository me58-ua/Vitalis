"""Persist conversational onboarding state.

Revision ID: 0024_add_onboarding_state
Revises: 0023_add_family_history
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0024_add_onboarding_state"
down_revision: Union[str, Sequence[str], None] = "0023_add_family_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_profiles",
        sa.Column("onboarding_state", sa.JSON(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("patient_profiles", "onboarding_state")
