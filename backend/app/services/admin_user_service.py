from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.users import AdminUserCreate, AdminUserUpdate


class AdminUserConflictError(Exception):
    pass


class AdminUserService:
    def __init__(self, users: UserRepository):
        self.users = users

    def create(self, data: AdminUserCreate) -> User:
        user = User(
            name=data.name,
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            tel=data.tel,
            birth_date=data.birth_date,
            gender=data.gender,
        )
        try:
            return self.users.create(user)
        except IntegrityError as error:
            raise AdminUserConflictError("Email or username is already registered") from error

    def update(self, user: User, data: AdminUserUpdate) -> User:
        values = data.model_dump(exclude_unset=True)
        password = values.pop("password", None)
        if password is not None:
            values["password_hash"] = hash_password(password)
        try:
            return self.users.update(user, values)
        except IntegrityError as error:
            raise AdminUserConflictError("Email or username is already registered") from error