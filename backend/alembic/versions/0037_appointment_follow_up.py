"""Add explicitly shared consultation notes and diagnoses."""
from alembic import op
import sqlalchemy as sa

revision = "0037_appointment_follow_up"
down_revision = "0036_late_prescriptions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("appointment_notes", sa.Column("shared_diagnosis", sa.Text()))
    op.add_column("appointment_notes", sa.Column("shared_notes", sa.Text()))


def downgrade():
    op.drop_column("appointment_notes", "shared_notes")
    op.drop_column("appointment_notes", "shared_diagnosis")
