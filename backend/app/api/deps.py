from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.repositories.profile_repository import ProfileRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService, InvalidAccessTokenError
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.health_document_repository import HealthDocumentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.privacy_repository import PrivacyRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.video_session_repository import VideoSessionRepository
from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService
from app.services.file_storage import LocalFileStorage
from app.config import settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
DbSession = Annotated[Session, Depends(get_db)]


def get_user_repository(db: DbSession) -> UserRepository:
    return UserRepository(db)


def get_profile_repository(db: DbSession) -> ProfileRepository:
    return ProfileRepository(db)


def get_appointment_repository(db: DbSession) -> AppointmentRepository:
    return AppointmentRepository(db)


def get_professional_repository(db: DbSession) -> ProfessionalRepository:
    return ProfessionalRepository(db)


def get_prescription_repository(db: DbSession) -> PrescriptionRepository:
    return PrescriptionRepository(db)


def get_health_document_repository(db: DbSession) -> HealthDocumentRepository:
    return HealthDocumentRepository(db)


def get_audit_repository(db: DbSession) -> AuditRepository:
    return AuditRepository(db)


def get_privacy_repository(db: DbSession) -> PrivacyRepository:
    return PrivacyRepository(db)


def get_chat_message_repository(db: DbSession) -> ChatMessageRepository:
    return ChatMessageRepository(db)


def get_video_session_repository(db: DbSession) -> VideoSessionRepository:
    return VideoSessionRepository(db)


def get_notification_repository(db: DbSession) -> NotificationRepository:
    return NotificationRepository(db)


def get_notification_service(
    repository: Annotated[NotificationRepository, Depends(get_notification_repository)],
) -> NotificationService:
    return NotificationService(repository)


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage(settings.FILE_STORAGE_PATH)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return AuthService(users).get_current_user(token)
    except InvalidAccessTokenError:
        raise credentials_exception

#para las funciones que solo el admin puede hacer
def get_current_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_current_patient(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")
    return current_user


def get_current_professional(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != UserRole.PROFESSIONAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional access required",
        )
    return current_user