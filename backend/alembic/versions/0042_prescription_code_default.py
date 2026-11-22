"""Generate prescription codes in the database."""
from alembic import op
import sqlalchemy as sa

revision = "0042_prescription_code_default"
down_revision = "0041_video_professional_no_show"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("prescriptions", "codigo", server_default=sa.text("gen_random_uuid()::text"))
    op.execute("UPDATE prescriptions SET codigo = id::text WHERE codigo IS NULL")


def downgrade():
    op.alter_column("prescriptions", "codigo", server_default=None)
