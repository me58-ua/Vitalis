"""Doctor-confirmed metadata for prescription documents; legacy values remain unknown."""
from alembic import op
import sqlalchemy as sa

revision = "0034_prescription_metadata"
down_revision = "0033_user_photo"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prescriptions", sa.Column("tipo", sa.String(20), nullable=True))
    op.add_column("prescriptions", sa.Column("titulo", sa.String(300), nullable=True))
    op.add_column("prescriptions", sa.Column("fecha_emision", sa.Date(), nullable=True))
    op.add_column("prescriptions", sa.Column("fecha_caducidad", sa.Date(), nullable=True))
    op.add_column("prescriptions", sa.Column("codigo", sa.String(100), nullable=True))
    op.create_check_constraint("ck_prescriptions_tipo", "prescriptions", "tipo IS NULL OR tipo IN ('medicacion', 'prueba', 'otro')")
    op.create_check_constraint("ck_prescriptions_dates", "prescriptions", "fecha_caducidad IS NULL OR (fecha_emision IS NOT NULL AND fecha_caducidad >= fecha_emision)")


def downgrade():
    op.drop_constraint("ck_prescriptions_dates", "prescriptions", type_="check")
    op.drop_constraint("ck_prescriptions_tipo", "prescriptions", type_="check")
    for column in ("codigo", "fecha_caducidad", "fecha_emision", "titulo", "tipo"):
        op.drop_column("prescriptions", column)
