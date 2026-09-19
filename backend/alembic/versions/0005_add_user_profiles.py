"""add patient and professional profiles

Revision ID: 0005_add_user_profiles
Revises: 0004_add_password_reset_tokens
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_add_user_profiles"
down_revision: Union[str, Sequence[str], None] = "0004_add_password_reset_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("blood_type", sa.String(length=10), nullable=True),
        sa.Column("allergies_summary", sa.String(length=255), nullable=True),
        sa.Column("chronic_conditions_summary", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=50), server_default="Europe/Madrid", nullable=False),
        sa.Column("language_preference", sa.String(length=10), server_default="es", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_patient_profiles_user_id", "patient_profiles", ["user_id"])

    op.create_table(
        "professional_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("specialty", sa.String(length=150), nullable=False),
        sa.Column("bio", sa.String(length=500), nullable=True),
        sa.Column("practice_address", sa.String(length=255), nullable=True),
        sa.Column("practice_phone", sa.String(length=50), nullable=True),
        sa.Column("is_accepting_new_patients", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("default_consultation_duration_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("telehealth_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_professional_profiles_user_id", "professional_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_professional_profiles_user_id", table_name="professional_profiles")
    op.drop_table("professional_profiles")
    op.drop_index("ix_patient_profiles_user_id", table_name="patient_profiles")
    op.drop_table("patient_profiles")