from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.users import AdminUserCreate, AdminUserUpdate
from app.models import AuditAction
from app.services.audit_service import AuditService


class AdminUserConflictError(Exception):
    pass


class AdminUserNotFoundError(Exception):
    pass


class AdminUserDeleteConflictError(Exception):
    pass


class AdminUserService:
    def __init__(self, users: UserRepository, audits: AuditRepository | None = None):
        self.users = users
        self.audit = AuditService(audits)

    def list(
        self,
        role: UserRole | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[User], int]:
        return self.users.list(role=role, search=search, offset=offset, limit=limit)

    def get(self, user_id) -> User:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise AdminUserNotFoundError("User not found")
        return user

    def create(self, data: AdminUserCreate) -> User:
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
            is_active=data.role != UserRole.PROFESSIONAL,
        )
        try:
            return self.users.create(user)
        except IntegrityError as error:
            self.users.rollback()
            raise AdminUserConflictError("Email or username is already registered") from error

    def update(self, user: User, data: AdminUserUpdate, actor: User | None = None) -> User:
        values = data.model_dump(exclude_unset=True)
        role_or_activation_changed = "role" in values or "is_active" in values
        password = values.pop("password", None)
        if password is not None:
            values["password_hash"] = hash_password(password)
        try:
            updated = self.users.update(user, values)
            if role_or_activation_changed and actor is not None:
                self.audit.record(
                    actor.id,
                    actor.role,
                    AuditAction.UPDATE,
                    "user_role",
                    user.id,
                )
            return updated
        except IntegrityError as error:
            self.users.rollback()
            raise AdminUserConflictError("Email or username is already registered") from error

    def delete(self, user_id, actor: User | None = None) -> None:
        user = self.get(user_id)
        try:
            self.users.delete(user)
            if actor is not None:
                self.audit.record(
                    actor.id,
                    actor.role,
                    AuditAction.DELETE,
                    "user",
                    user.id,
                )
        except IntegrityError as error:
            self.users.rollback()
            raise AdminUserDeleteConflictError(
                "User cannot be deleted because related records exist"
            ) from error