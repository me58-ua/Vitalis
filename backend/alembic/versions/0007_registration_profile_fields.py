"""add registration consent and remove language preference

Revision ID: 0007_registration_profile_fields
Revises: 0006_prof_patient_assignments
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_registration_profile_fields"
down_revision: Union[str, Sequence[str], None] = "0006_prof_patient_assignments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terms_accepted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.drop_column("patient_profiles", "language_preference")


def downgrade() -> None:
    op.add_column(
        "patient_profiles",
        sa.Column("language_preference", sa.String(length=10), server_default="es", nullable=False),
    )
    op.drop_column("users", "terms_accepted")