from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.models.password_reset_token import PasswordResetToken


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def invalidate_password_reset_tokens(self, user_id) -> None:
        self.session.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        ).update({PasswordResetToken.used_at: func.now()}, synchronize_session=False)

    def create_password_reset_token(self, reset_token: PasswordResetToken) -> PasswordResetToken:
        self.session.add(reset_token)
        self.session.flush()
        return reset_token

    def get_active_password_reset_token(self, token_hash: str) -> PasswordResetToken | None:
        return self.session.scalar(
            select(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
            )
            .with_for_update()
        )