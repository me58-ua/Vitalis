"""Link audited patients to their user accounts, preserving existing audit rows."""
from alembic import op
import sqlalchemy as sa

revision = "0027_audit_patient_user"
down_revision = "0026_drop_body_measured_at"
branch_labels = None
depends_on = None


def _drop_patient_fk():
    for constraint in sa.inspect(op.get_bind()).get_foreign_keys("audit_logs"):
        if constraint["constrained_columns"] == ["patient_id"]:
            op.drop_constraint(constraint["name"], "audit_logs", type_="foreignkey")


def upgrade():
    _drop_patient_fk()
    op.execute("""UPDATE audit_logs AS a SET patient_id = p.user_id
                  FROM patient_profiles AS p WHERE a.patient_id = p.id""")
    op.create_foreign_key("fk_audit_patient_user", "audit_logs", "users", ["patient_id"], ["id"], ondelete="SET NULL")


def downgrade():
    _drop_patient_fk()
    # A patient account without a profile has no corresponding old identifier.
    # Preserve its audit row with a null patient link on downgrade.
    op.execute("""UPDATE audit_logs AS a SET patient_id =
                  (SELECT p.id FROM patient_profiles AS p WHERE p.user_id = a.patient_id)
                  WHERE a.patient_id IS NOT NULL""")
    op.create_foreign_key("fk_audit_patient_profile", "audit_logs", "patient_profiles", ["patient_id"], ["id"], ondelete="SET NULL")
