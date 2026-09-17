"""add username to users

Revision ID: 0003_add_username_to_users
Revises: 0002_add_user_profile_fields
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_username_to_users"
down_revision: Union[str, Sequence[str], None] = "0002_add_user_profile_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE users
            SET username = split_part(email, '@', 1)
            WHERE username IS NULL
            """
        )
    )
    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")