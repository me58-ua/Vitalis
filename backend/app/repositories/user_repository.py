from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken


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

    def list(
        self,
        role: UserRole | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[User], int]:
        query = select(User)
        count_query = select(func.count()).select_from(User)
        filters = []
        if role is not None:
            filters.append(User.role == role)
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    User.name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.username.ilike(search_pattern),
                )
            )
        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)
        users = list(self.session.scalars(query.order_by(User.created_at.desc()).offset(offset).limit(limit)))
        total = self.session.scalar(count_query) or 0
        return users, total

    def update(self, user: User, values: dict) -> User:
        for field, value in values.items():
            setattr(user, field, value)
        self.session.flush()
        return user

    def delete(self, user: User) -> None:
        self.session.delete(user)
        self.session.flush()

    def rollback(self) -> None:
        self.session.rollback()

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

    def create_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        self.session.add(refresh_token)
        self.session.flush()
        return refresh_token

    def get_active_refresh_token(self, token_hash: str) -> RefreshToken | None:
        return self.session.scalar(
            select(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            .with_for_update()
        )