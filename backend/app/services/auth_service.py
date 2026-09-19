from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, hash_password, verify_password
from app.models import PatientProfile, ProfessionalProfile, User, UserRole
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


class AuthService:
    def __init__(self, users: UserRepository):
        self.users = users

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
                address=data.address,
                blood_type=data.blood_type,
                allergies_summary=data.allergies_summary,
                chronic_conditions_summary=data.chronic_conditions_summary,
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
            )
        try:
            return self.users.create(user)
        except IntegrityError as error:
            if "username" in str(error.orig).lower():
                raise UsernameAlreadyRegisteredError from error
            raise EmailAlreadyRegisteredError from error

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

    def issue_access_token(self, user: User) -> str:
        return create_access_token(str(user.id), user.role.value, getattr(user, "session_version", 0) or 0)