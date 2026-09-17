"""add user profile fields

Revision ID: 0002_add_user_profile_fields
Revises: 0001_create_users
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_user_profile_fields"
down_revision: Union[str, Sequence[str], None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("tel", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(length=50), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE users
            SET name = split_part(email, '@', 1),
                tel = '+34000000000',
                birth_date = DATE '1970-01-01'
            WHERE name IS NULL
            """
        )
    )

    op.alter_column("users", "name", nullable=False)
    op.alter_column("users", "tel", nullable=False)
    op.alter_column("users", "birth_date", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "gender")
    op.drop_column("users", "birth_date")
    op.drop_column("users", "tel")
    op.drop_column("users", "name")