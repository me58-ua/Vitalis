"""add professional license and approval state

Revision ID: 0014_professional_approval
Revises: 0013_add_patient_health_models
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014_professional_approval"
down_revision: Union[str, Sequence[str], None] = "0013_add_patient_health_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("professional_profiles", sa.Column("license_number", sa.String(50), nullable=True))
    op.add_column("professional_profiles", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("professional_profiles", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("professional_profiles", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    approval_status = postgresql.ENUM("pending", "approved", "rejected", name="professional_approval_status", create_type=False)
    approval_status.create(op.get_bind(), checkfirst=True)
    op.add_column("professional_profiles", sa.Column("approval_status", approval_status, server_default="pending", nullable=False))
    op.execute(
        sa.text(
            "UPDATE professional_profiles SET license_number = 'legacy-' || replace(id::text, '-', '') "
            "WHERE license_number IS NULL"
        )
    )
    op.alter_column("professional_profiles", "license_number", nullable=False)
    op.create_unique_constraint("uq_professional_profiles_license_number", "professional_profiles", ["license_number"])
    op.create_index("ix_professional_profiles_license_number", "professional_profiles", ["license_number"])


def downgrade() -> None:
    op.drop_index("ix_professional_profiles_license_number", table_name="professional_profiles")
    op.drop_constraint("uq_professional_profiles_license_number", "professional_profiles", type_="unique")
    op.drop_column("professional_profiles", "approval_status")
    op.drop_column("professional_profiles", "created_at")
    op.drop_column("professional_profiles", "reviewed_at")
    op.drop_column("professional_profiles", "rejection_reason")
    op.drop_column("professional_profiles", "license_number")
    op.execute("DROP TYPE IF EXISTS professional_approval_status")