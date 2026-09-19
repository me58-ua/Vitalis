"""add required DNI to users

Revision ID: 0008_add_dni_to_users
Revises: 0007_registration_profile_fields
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_add_dni_to_users"
down_revision: Union[str, Sequence[str], None] = "0007_registration_profile_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("dni", sa.String(length=20), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE users
            SET dni = 'L' || substr(md5(id::text), 1, 19)
            WHERE dni IS NULL
            """
        )
    )
    op.alter_column("users", "dni", nullable=False)
    op.create_index("ix_users_dni", "users", ["dni"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_dni", table_name="users")
    op.drop_column("users", "dni")