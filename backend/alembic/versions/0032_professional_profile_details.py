"""Professional experience, spoken languages and email preference."""
from alembic import op
import sqlalchemy as sa

revision = "0032_profile_details"
down_revision = "0031_spontaneous_chats"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("professional_profiles", sa.Column("years_experience", sa.Integer(), nullable=True))
    op.add_column("professional_profiles", sa.Column("languages", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("professional_profiles", sa.Column("email_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_check_constraint("ck_professional_experience", "professional_profiles", "years_experience IS NULL OR years_experience BETWEEN 0 AND 80")


def downgrade():
    op.drop_constraint("ck_professional_experience", "professional_profiles", type_="check")
    for name in ("email_notifications_enabled", "languages", "years_experience"):
        op.drop_column("professional_profiles", name)
