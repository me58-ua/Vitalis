# Servicio de autenticación: registra usuarios, valida credenciales y gestiona tokens de acceso y actualización.
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from jose import JWTError

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import PatientProfile, ProfessionalProfile, RefreshToken, User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegisterRequest


class EmailAlreadyRegisteredError(Exception):
    def __init__(self) -> None:
        super().__init__("A user with this email already exists")


class UsernameAlreadyRegisteredError(Exception):
    def __init__(self) -> None:
        super().__init__("A user with this username already exists")


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class InvalidAccessTokenError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


class AuthService:
    def __init__(self, users: UserRepository, notifications=None):
        self.users = users
        self.notifications = notifications

    def register_user(self, data: UserRegisterRequest) -> User:
        if self.users.get_by_email(data.email) is not None:
            raise EmailAlreadyRegisteredError
        if self.users.get_by_username(data.username) is not None:
            raise UsernameAlreadyRegisteredError

        user = User(
            name=data.name,
            dni=data.dni,
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            tel=data.tel,
            birth_date=data.birth_date,
            gender=data.gender,
            terms_accepted=data.terms_accepted,
            is_active=data.role == UserRole.PATIENT,
        )
        if data.role == UserRole.PATIENT:
            user.patient_profile = PatientProfile(
                birth_date=data.birth_date,
                height_cm=data.height_cm,
                weight_kg=data.weight_kg,
                address=data.address,
                blood_type=data.blood_type,
                timezone=data.timezone,
            )
        else:
            user.professional_profile = ProfessionalProfile(
                specialty=data.specialty,
                bio=data.bio,
                practice_address=data.practice_address,
                practice_phone=data.practice_phone,
                is_accepting_new_patients=data.is_accepting_new_patients,
                default_consultation_duration_minutes=data.default_consultation_duration_minutes,
                telehealth_enabled=data.telehealth_enabled,
                license_number=data.license_number,
            )
        try:
            user = self.users.create(user)
        except IntegrityError as error:
            if "username" in str(error.orig).lower():
                raise UsernameAlreadyRegisteredError from error
            raise EmailAlreadyRegisteredError from error
        if user.role == UserRole.PROFESSIONAL and self.notifications is not None:
            self.notifications.notify_professional_review(user)
        return user

    def register_patient(self, data: UserRegisterRequest) -> User:
        return self.register_user(data)

    def authenticate(self, identifier: str, password: str) -> User:
        identifier = identifier.strip().lower()
        user = self.users.get_by_email(identifier)
        if user is None:
            user = self.users.get_by_username(identifier)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        return user

    def get_current_user(self, token: str) -> User:
        try:
            payload = decode_access_token(token)
            subject = payload.get("sub")
            user_id = UUID(subject) if isinstance(subject, str) else None
            session_id = UUID(payload["sid"])
        except (JWTError, ValueError, KeyError, TypeError, AttributeError):
            raise InvalidAccessTokenError

        user = self.users.get_by_id(user_id) if user_id else None
        token_session_version = payload.get("session_version", 0)
        refresh_session = self.users.get_refresh_session(session_id)
        if (
            user is None
            or not user.is_active
            or not isinstance(token_session_version, int)
            or token_session_version != user.session_version
            or refresh_session is None
            or refresh_session.user_id != user.id
            or not self._valid_session(refresh_session, user)
        ):
            raise InvalidAccessTokenError
        return user

    def _access_for_session(self, user: User, session_id: UUID) -> str:
        return create_access_token(str(user.id), user.role.value, user.session_version, str(session_id))

    @staticmethod
    def _valid_session(session: RefreshToken, user: User) -> bool:
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return session.revoked_at is None and expires > datetime.now(timezone.utc) and session.session_version == user.session_version

    def logout(self, current_user: User, access_token: str) -> None:
        """Revoke this login session, leaving other logins and accounts untouched."""
        try:
            session_id = UUID(decode_access_token(access_token)["sid"])
        except (JWTError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise InvalidAccessTokenError from error
        session = self.users.get_refresh_session(session_id, lock=True)
        if session is None or session.user_id != current_user.id:
            raise InvalidAccessTokenError
        session.revoked_at = datetime.now(timezone.utc)
        self.users.session.flush()

    def issue_tokens(self, user: User) -> tuple[str, str]:
        raw_token = create_refresh_token()
        refresh_token = RefreshToken(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token),
            session_version=user.session_version,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.users.create_refresh_token(refresh_token)
        return self._access_for_session(user, refresh_token.id), raw_token

    def refresh_tokens(self, raw_token: str) -> tuple[str, str]:
        refresh_token = self.users.get_active_refresh_token(hash_refresh_token(raw_token))
        if refresh_token is None:
            raise InvalidRefreshTokenError

        user = self.users.get_by_id(refresh_token.user_id)
        if (
            user is None
            or not user.is_active
            or not self._valid_session(refresh_token, user)
        ):
            raise InvalidRefreshTokenError

        # Rotate the secret while keeping a stable login ID for access validation
        # and logout, including when refresh and logout requests race.
        new_token = create_refresh_token()
        refresh_token.token_hash = hash_refresh_token(new_token)
        refresh_token.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        self.users.session.flush()
        return self._access_for_session(user, refresh_token.id), new_token
