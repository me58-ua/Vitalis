# Servicio de recuperación de contraseña: genera, valida y aplica tokens de restablecimiento.
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.core.security import (
    create_password_reset_token,
    hash_password,
    hash_password_reset_token,
)
from app.core.rate_limit import password_reset_rate_limiter
from app.models import User
from app.models.password_reset_token import PasswordResetToken
from app.repositories.user_repository import UserRepository


class InvalidPasswordResetToken(Exception):
    pass


class PasswordResetService:
    def __init__(self, users: UserRepository):
        self.users = users

    def issue_token(self, user: User) -> str:
        self.users.invalidate_password_reset_tokens(user.id)
        raw_token = create_password_reset_token()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_password_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
        self.users.create_password_reset_token(reset_token)
        return raw_token

    def request_reset(self, email: str, client_host: str) -> tuple[User, str] | None:
        if not password_reset_rate_limiter.allow(f"ip:{client_host}"):
            return None
        if not password_reset_rate_limiter.allow(f"email:{email}"):
            return None

        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        return user, self.issue_token(user)

    def reset_password(self, raw_token: str, password: str) -> User:
        reset_token = self.users.get_active_password_reset_token(
            hash_password_reset_token(raw_token)
        )
        now = datetime.now(timezone.utc)
        if reset_token is None or reset_token.expires_at <= now:
            raise InvalidPasswordResetToken("El enlace de recuperacion no es valido o ha expirado")

        user = self.users.get_by_id(reset_token.user_id)
        if user is None or not user.is_active:
            raise InvalidPasswordResetToken("El enlace de recuperacion no es valido o ha expirado")

        user.password_hash = hash_password(password)
        user.session_version += 1
        reset_token.used_at = now
        self.users.session.flush()
        return user
