"""add AI processing consent to patient profiles

Revision ID: 0021_add_ai_processing_consent
Revises: 0020_add_notifications
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0021_add_ai_processing_consent"
down_revision: Union[str, Sequence[str], None] = "0020_add_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patient_profiles",
        sa.Column("ai_processing_consent", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "patient_profiles",
        sa.Column("ai_processing_consent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patient_profiles", "ai_processing_consent_at")
    op.drop_column("patient_profiles", "ai_processing_consent")
