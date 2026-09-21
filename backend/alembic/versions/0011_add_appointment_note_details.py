"""add clinical notes and patient summary to appointment notes

Revision ID: 0011_add_note_details
Revises: 0010_add_appointment_notes
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_add_note_details"
down_revision: Union[str, Sequence[str], None] = "0010_add_appointment_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointment_notes", sa.Column("clinical_notes", sa.Text(), nullable=True))
    op.add_column("appointment_notes", sa.Column("patient_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("appointment_notes", "patient_summary")
    op.drop_column("appointment_notes", "clinical_notes")