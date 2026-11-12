"""Optional user profile photo reference."""
from alembic import op
import sqlalchemy as sa

revision = "0033_user_photo"
down_revision = "0032_profile_details"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("photo_url", sa.String(2048), nullable=True))


def downgrade():
    op.drop_column("users", "photo_url")
