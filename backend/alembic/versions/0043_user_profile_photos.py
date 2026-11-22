"""Store uploaded profile photos."""
from alembic import op
import sqlalchemy as sa

revision = "0043_user_profile_photos"
down_revision = "0042_prescription_code_default"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("photo_content", sa.LargeBinary(), nullable=True))


def downgrade():
    op.execute("UPDATE users SET photo_url = NULL WHERE photo_content IS NOT NULL")
    op.drop_column("users", "photo_content")
