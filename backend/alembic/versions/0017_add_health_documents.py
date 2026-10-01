"""add patient health documents

Revision ID: 0017_add_health_documents
Revises: 0016_add_prescriptions
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0017_add_health_documents"
down_revision: Union[str, Sequence[str], None] = "0016_add_prescriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "health_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("fecha_subida", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_health_documents_patient", "health_documents", ["patient_id"])
    op.create_index("idx_health_documents_tipo", "health_documents", ["tipo"])


def downgrade() -> None:
    op.drop_index("idx_health_documents_tipo", table_name="health_documents")
    op.drop_index("idx_health_documents_patient", table_name="health_documents")
    op.drop_table("health_documents")