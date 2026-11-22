# Servicio de administración de usuarios: lista, consulta, crea, actualiza y elimina usuarios.
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models import PatientProfile, ProfessionalProfile, ProfessionalApprovalStatus, User, UserRole
from app.repositories.user_repository import UserRepository, user_identifier_conflict_code
from app.repositories.audit_repository import AuditRepository
from app.schemas.users import AdminUserCreate, AdminUserUpdate
from app.models import AuditAction
from app.services.audit_service import AuditService


class AdminUserConflictError(Exception):
    pass


class AdminUserNotFoundError(Exception):
    pass


class AdminUserValidationError(Exception):
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
            photo_url=data.photo_url,
            is_active=data.role != UserRole.PROFESSIONAL,
        )
        if data.role == UserRole.PATIENT:
            values = data.patient_profile.model_dump() if data.patient_profile else {}
            user.patient_profile = PatientProfile(birth_date=data.birth_date, **values)
        elif data.role == UserRole.PROFESSIONAL:
            # The request schema requires professional fields for this role.
            if data.professional_profile is None:
                raise AdminUserValidationError("PROFESSIONAL_PROFILE_REQUIRED")
            user.professional_profile = ProfessionalProfile(**data.professional_profile.model_dump())
        try:
            return self.users.create(user)
        except IntegrityError as error:
            self.users.rollback()
            raise AdminUserConflictError(user_identifier_conflict_code(error)) from error

    def update(self, user: User, data: AdminUserUpdate, actor: User | None = None) -> User:
        values = data.model_dump(exclude_unset=True)
        if "photo_url" in values and values["photo_url"] != user.photo_url:
            values["photo_content"] = None
        patient = values.pop("patient_profile", None)
        professional = values.pop("professional_profile", None)
        role = data.role or user.role
        if (patient is not None and role != UserRole.PATIENT) or (professional is not None and role != UserRole.PROFESSIONAL):
            raise AdminUserValidationError("PROFILE_ROLE_MISMATCH")
        if role == UserRole.PROFESSIONAL and user.professional_profile is None and professional is None:
            raise AdminUserValidationError("PROFESSIONAL_PROFILE_REQUIRED")
        if role == UserRole.PROFESSIONAL:
            profile = user.professional_profile
            approved = profile is not None and profile.approval_status == ProfessionalApprovalStatus.APPROVED
            if data.is_active is True and not approved:
                raise AdminUserValidationError("PROFESSIONAL_APPROVAL_REQUIRED")
            if not approved:
                values["is_active"] = False
        role_or_activation_changed = "role" in values or "is_active" in values
        password = values.pop("password", None)
        if password is not None:
            values["password_hash"] = hash_password(password)
        try:
            if role == UserRole.PATIENT:
                if user.patient_profile is None:
                    user.patient_profile = PatientProfile(birth_date=data.birth_date or user.birth_date)
                if patient is not None:
                    for field, value in patient.items():
                        setattr(user.patient_profile, field, value)
                if data.birth_date is not None:
                    user.patient_profile.birth_date = data.birth_date
            elif role == UserRole.PROFESSIONAL and professional is not None:
                if user.professional_profile is None:
                    user.professional_profile = ProfessionalProfile(**professional)
                else:
                    for field, value in professional.items():
                        setattr(user.professional_profile, field, value)
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
            raise AdminUserConflictError(user_identifier_conflict_code(error)) from error

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
