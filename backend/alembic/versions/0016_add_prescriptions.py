"""add prescriptions and late-issue authorizations

Revision ID: 0016_add_prescriptions
Revises: 0015_professional_reviewer
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0016_add_prescriptions"
down_revision: Union[str, Sequence[str], None] = "0015_professional_reviewer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prescriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["professional_id"], ["professional_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id"),
    )
    op.create_index("idx_prescriptions_patient", "prescriptions", ["patient_id"])
    op.create_index("idx_prescriptions_professional", "prescriptions", ["professional_id"])

    op.create_table(
        "prescription_authorizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authorized_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["authorized_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id"),
    )
    op.create_index("idx_prescription_authorizations_appointment", "prescription_authorizations", ["appointment_id"])


def downgrade() -> None:
    op.drop_index("idx_prescription_authorizations_appointment", table_name="prescription_authorizations")
    op.drop_table("prescription_authorizations")
    op.drop_index("idx_prescriptions_professional", table_name="prescriptions")
    op.drop_index("idx_prescriptions_patient", table_name="prescriptions")
    op.drop_table("prescriptions")