"""Record the patient's health sharing choice when booking."""
import sqlalchemy as sa
from alembic import op

revision = "0039_appointment_health_sharing"
down_revision = "0038_modality_working_hours"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("appointments", sa.Column("health_sharing", sa.String(5), nullable=True))
    op.create_check_constraint(
        "valid_appointment_health_sharing", "appointments",
        "health_sharing IN ('none', 'basic', 'full')",
    )


def downgrade():
    op.drop_constraint("valid_appointment_health_sharing", "appointments", type_="check")
    op.drop_column("appointments", "health_sharing")
