"""Expand family medical history without changing existing category values."""
from alembic import op
import sqlalchemy as sa

revision = "0035_expand_family_history"
down_revision = "0034_prescription_metadata"
branch_labels = None
depends_on = None

OLD = ('diabetes', 'cancer', 'cardiovascular', 'huntington', 'otro')
NEW = (*OLD, 'hypertension', 'high_cholesterol', 'stroke', 'osteoporosis',
       'cystic_fibrosis', 'sickle_cell_disease', 'familial_hypercholesterolemia')


def constraint(values):
    return 'condition_category IN (' + ', '.join(repr(value) for value in values) + ')'


def upgrade():
    op.drop_constraint('ck_family_condition_values', 'family_history_entries', type_='check')
    op.alter_column('family_history_entries', 'condition_category', type_=sa.String(40))
    op.create_check_constraint('ck_family_condition_values', 'family_history_entries', constraint(NEW))
    op.add_column('family_history_entries', sa.Column('relative_detail', sa.String(100), nullable=True))
    op.add_column('family_history_entries', sa.Column('notes', sa.String(500), nullable=True))
    # family_ + familial_hypercholesterolemia exceeds the previous width.
    op.alter_column('risk_snapshots', 'model', type_=sa.String(60))


def downgrade():
    # Refuse to silently discard or reclassify the new categories.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM family_history_entries WHERE condition_category NOT IN ('diabetes','cancer','cardiovascular','huntington','otro') LIMIT 1")).first():
        raise RuntimeError('New family history categories exist; export or migrate them before downgrading.')
    if connection.execute(sa.text('SELECT 1 FROM risk_snapshots WHERE length(model) > 40 LIMIT 1')).first():
        raise RuntimeError('Expanded family risk snapshots exist; migrate them before downgrading.')
    op.drop_column('family_history_entries', 'notes')
    op.drop_column('family_history_entries', 'relative_detail')
    op.drop_constraint('ck_family_condition_values', 'family_history_entries', type_='check')
    op.create_check_constraint('ck_family_condition_values', 'family_history_entries', constraint(OLD))
    op.alter_column('family_history_entries', 'condition_category', type_=sa.String(30))
    op.alter_column('risk_snapshots', 'model', type_=sa.String(40))
