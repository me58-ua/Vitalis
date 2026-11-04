"""add selective audit logs

Revision ID: 0018_add_audit_logs
Revises: 0017_add_health_documents
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0018_add_audit_logs"
down_revision: Union[str, Sequence[str], None] = "0017_add_health_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    audit_action = postgresql.ENUM(
        "lectura", "creacion", "modificacion", "eliminacion", name="audit_action", create_type=False
    )
    audit_action.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", postgresql.ENUM(
            "patient", "professional", "admin", name="user_role", create_type=False
        ), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accion", audit_action, nullable=False),
        sa.Column("entidad", sa.String(length=80), nullable=False),
        sa.Column("entidad_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fecha_hora", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_logs_patient", "audit_logs", ["patient_id"])
    op.create_index("idx_audit_logs_entity", "audit_logs", ["entidad", "entidad_id"])
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["fecha_hora"])


def downgrade() -> None:
    op.drop_index("idx_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_entity", table_name="audit_logs")
    op.drop_index("idx_audit_logs_patient", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS audit_action")
