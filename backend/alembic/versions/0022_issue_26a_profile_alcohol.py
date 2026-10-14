"""Issue 26A profile fields, alcohol logs, and canonical habit enum.

Revision ID: 0022_issue_26a_profile_alcohol
Revises: 0021_add_ai_processing_consent
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0022_issue_26a_profile_alcohol"
down_revision: Union[str, Sequence[str], None] = "0021_add_ai_processing_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patient_profiles", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("patient_profiles", sa.Column("sex_at_birth", sa.String(30), nullable=True))
    op.add_column("patient_profiles", sa.Column("height_cm", sa.Numeric(5, 2), nullable=True))
    op.add_column("patient_profiles", sa.Column("weight_kg", sa.Numeric(6, 2), nullable=True))
    op.add_column("patient_profiles", sa.Column("body_measured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("patient_profiles", sa.Column("family_history_reviewed", sa.Boolean(), server_default="false", nullable=False))
    op.create_check_constraint("ck_patient_height_range", "patient_profiles", "height_cm IS NULL OR height_cm BETWEEN 100 AND 250")
    op.create_check_constraint("ck_patient_weight_range", "patient_profiles", "weight_kg IS NULL OR weight_kg BETWEEN 25 AND 400")

    op.execute("DELETE FROM habit_logs WHERE tipo = 'alcohol'")
    op.execute("ALTER TYPE habit_type RENAME TO habit_type_old")
    op.execute("CREATE TYPE habit_type AS ENUM ('sueno', 'ejercicio', 'dieta', 'tabaco')")
    op.execute("ALTER TABLE habit_logs ALTER COLUMN tipo TYPE habit_type USING tipo::text::habit_type")
    op.execute("DROP TYPE habit_type_old")

    op.create_table(
        "alcohol_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("binge", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("frequency BETWEEN 0 AND 4", name="ck_alcohol_frequency_range"),
        sa.CheckConstraint("quantity IS NULL OR quantity BETWEEN 0 AND 4", name="ck_alcohol_quantity_range"),
        sa.CheckConstraint("binge IS NULL OR binge BETWEEN 0 AND 4", name="ck_alcohol_binge_range"),
        sa.CheckConstraint(
            "(frequency = 0 AND quantity IS NULL AND binge IS NULL) OR "
            "(frequency > 0 AND quantity IS NOT NULL AND binge IS NOT NULL)",
            name="ck_alcohol_response_coherence",
        ),
    )
    op.create_index("ix_alcohol_logs_patient_id", "alcohol_logs", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_alcohol_logs_patient_id", table_name="alcohol_logs")
    op.drop_table("alcohol_logs")
    # Reintroduce the legacy value only for databases explicitly downgraded.
    op.execute("ALTER TYPE habit_type RENAME TO habit_type_new")
    op.execute("CREATE TYPE habit_type AS ENUM ('sueno', 'ejercicio', 'dieta', 'tabaco', 'alcohol')")
    op.execute("ALTER TABLE habit_logs ALTER COLUMN tipo TYPE habit_type USING tipo::text::habit_type")
    op.execute("DROP TYPE habit_type_new")
    op.drop_constraint("ck_patient_weight_range", "patient_profiles", type_="check")
    op.drop_constraint("ck_patient_height_range", "patient_profiles", type_="check")
    for column in ("family_history_reviewed", "body_measured_at", "weight_kg", "height_cm", "sex_at_birth", "birth_date"):
        op.drop_column("patient_profiles", column)
