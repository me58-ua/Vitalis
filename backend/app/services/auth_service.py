from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegisterRequest


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class AuthService:
    def __init__(self, users: UserRepository):
        self.users = users

    def register_patient(self, data: UserRegisterRequest) -> User:
        if self.users.get_by_email(data.email) is not None:
            raise EmailAlreadyRegisteredError

        user = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            role=UserRole.PATIENT,
            tel=data.tel,
            birth_date=data.birth_date,
            gender=data.gender,
        )
        try:
            return self.users.create(user)
        except IntegrityError as error:
            raise EmailAlreadyRegisteredError from error

    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email.lower())
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        return user

    def issue_access_token(self, user: User) -> str:
        return create_access_token(str(user.id), user.role.value)