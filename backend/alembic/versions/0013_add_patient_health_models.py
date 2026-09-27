"""add structured patient health models and consent

Revision ID: 0013_add_patient_health_models
Revises: 0012_add_refresh_tokens
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0013_add_patient_health_models"
down_revision: Union[str, Sequence[str], None] = "0012_add_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patient_profiles", sa.Column("onboarding_completed", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("patient_profiles", sa.Column("share_health_data", sa.Boolean(), server_default="false", nullable=False))
    op.drop_column("patient_profiles", "allergies_summary")
    op.drop_column("patient_profiles", "chronic_conditions_summary")

    allergy_severity = postgresql.ENUM(
        "leve", "moderada", "grave", "mortal", name="allergy_severity", create_type=False
    )
    habit_type = postgresql.ENUM(
        "sueno", "ejercicio", "dieta", "tabaco", "alcohol", name="habit_type", create_type=False
    )
    allergy_severity.create(op.get_bind(), checkfirst=True)
    habit_type.create(op.get_bind(), checkfirst=True)

    for table, columns in {
        "allergies": [
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("nombre", sa.String(150), nullable=False), sa.Column("gravedad", allergy_severity, nullable=False),
            sa.Column("fecha_registro", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
        "chronic_conditions": [
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("nombre_condicion", sa.String(200), nullable=False), sa.Column("fecha_diagnostico", sa.Date(), nullable=True),
            sa.Column("activa", sa.Boolean(), server_default="true", nullable=False), sa.Column("fecha_registro", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
        "medications": [
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("nombre", sa.String(200), nullable=False), sa.Column("dosis", sa.String(150), nullable=False), sa.Column("frecuencia", sa.String(150), nullable=False),
            sa.Column("fecha_inicio", sa.Date(), nullable=True), sa.Column("fecha_fin", sa.Date(), nullable=True), sa.Column("activa", sa.Boolean(), server_default="true", nullable=False), sa.Column("fecha_registro", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
        "habit_logs": [
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tipo", habit_type, nullable=False), sa.Column("valor", sa.Numeric(), nullable=True), sa.Column("unidad", sa.String(50), nullable=False), sa.Column("fecha", sa.Date(), nullable=False),
        ],
    }.items():
        op.create_table(table, *columns, sa.ForeignKeyConstraint(["patient_id"], ["patient_profiles.id"], ondelete="CASCADE"))
        op.create_index(f"ix_{table}_patient_id", table, ["patient_id"])


def downgrade() -> None:
    for table in ("habit_logs", "medications", "chronic_conditions", "allergies"):
        op.drop_index(f"ix_{table}_patient_id", table_name=table)
        op.drop_table(table)
    op.execute("DROP TYPE IF EXISTS habit_type")
    op.execute("DROP TYPE IF EXISTS allergy_severity")
    op.add_column("patient_profiles", sa.Column("allergies_summary", sa.String(255), nullable=True))
    op.add_column("patient_profiles", sa.Column("chronic_conditions_summary", sa.String(255), nullable=True))
    op.drop_column("patient_profiles", "share_health_data")
    op.drop_column("patient_profiles", "onboarding_completed")