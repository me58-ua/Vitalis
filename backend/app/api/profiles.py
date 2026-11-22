from io import BytesIO
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from PIL import Image, ImageOps

from app.api.deps import (
    get_current_user,
    get_current_patient,
    get_current_professional,
    get_profile_repository,
    get_user_repository,
    get_notification_service,
)
from app.models import AuditAction, User
from app.core.rate_limit import patient_password_change_limiter
from app.api.deps import get_audit_repository
from app.repositories.audit_repository import AuditRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserResponse
from app.schemas.profiles import (
    BasicUserUpdate,
    ChangePasswordRequest,
    PatientProfileResponse,
    PatientProfileUpdate,
    ProfessionalProfileResponse,
    ProfessionalProfileUpdate,
    ProfessionalNotificationSettings,
)
from app.schemas.health import AIConsentUpdate
from app.services.audit_service import AuditService
from app.services.email_service import send_password_changed_email
from app.services.notification_service import NotificationService
from app.services.profile_service import (
    InvalidCurrentPasswordError,
    ProfileNotFoundError,
    ProfileService,
)
from app.services.profile_change_service import ProfileChangeValidation


router = APIRouter(tags=["profiles"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Users = Annotated[UserRepository, Depends(get_user_repository)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]
PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024
PROFILE_PHOTO_MAX_PIXELS = 16_000_000


@router.put("/users/me/photo", response_model=UserResponse)
def upload_profile_photo(
    current_user: Annotated[User, Depends(get_current_user)],
    users: Users,
    file: UploadFile = File(...),
) -> User:
    raw = file.file.read(PROFILE_PHOTO_MAX_BYTES + 1)
    if len(raw) > PROFILE_PHOTO_MAX_BYTES:
        raise HTTPException(413, detail="PROFILE_PHOTO_TOO_LARGE")
    try:
        with Image.open(BytesIO(raw), formats=("JPEG", "PNG", "WEBP")) as source:
            if source.width * source.height > PROFILE_PHOTO_MAX_PIXELS:
                raise HTTPException(413, detail="PROFILE_PHOTO_TOO_LARGE")
            photo = ImageOps.exif_transpose(source).convert("RGB")
            photo.thumbnail((384, 384))
            output = BytesIO()
            photo.save(output, format="JPEG", quality=85)
    except Image.DecompressionBombError:
        raise HTTPException(413, detail="PROFILE_PHOTO_TOO_LARGE") from None
    except (OSError, ValueError, SyntaxError):
        raise HTTPException(422, detail="PROFILE_PHOTO_INVALID") from None
    url = f"/profile-photos/{current_user.id}/{uuid4()}.jpg"
    return users.update(current_user, {"photo_url": url, "photo_content": output.getvalue()})


@router.get("/profile-photos/{user_id}/{photo_id}.jpg", response_class=Response, include_in_schema=False)
def get_profile_photo(user_id: UUID, photo_id: UUID, users: Users) -> Response:
    photo = users.get_profile_photo(user_id, f"/profile-photos/{user_id}/{photo_id}.jpg")
    if photo is None:
        raise HTTPException(404, detail="PROFILE_PHOTO_NOT_FOUND")
    return Response(photo, media_type="image/jpeg", headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/patients/me/profile", response_model=PatientProfileResponse)
def get_patient_profile(current_user: CurrentPatient, profiles: Profiles):
    try:
        return ProfileService(None, profiles).get_patient_profile(current_user)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/patients/me/profile", response_model=PatientProfileResponse)
def update_patient_profile(
    data: PatientProfileUpdate,
    current_user: CurrentPatient,
    profiles: Profiles,
):
    if data.model_fields_set & {'height_cm', 'weight_kg', 'blood_type'}:
        raise HTTPException(status_code=409, detail='Actualiza tus datos de salud mediante el asistente IA y confirma el resumen.')
    try:
        return ProfileService(None, profiles).update_patient_profile(current_user, data)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/patients/me/ai-consent", response_model=PatientProfileResponse)
def update_ai_consent(
    data: AIConsentUpdate,
    current_user: CurrentPatient,
    profiles: Profiles,
    audits: Audits,
):
    service = ProfileService(None, profiles)
    try:
        profile = service.update_ai_consent(current_user, data.ai_processing_consent)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    AuditService(audits).record(
        current_user.id,
        current_user.role,
        AuditAction.UPDATE,
        "patient_profile",
        profile.id,
        current_user.id,
    )
    return profile


@router.patch("/patients/me", response_model=UserResponse)
def update_patient(data: BasicUserUpdate, current_user: CurrentPatient, users: Users):
    return ProfileService(users, None).update_basic_user(current_user, data)


@router.post("/patients/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_patient_password(
    data: ChangePasswordRequest, current_user: CurrentPatient, users: Users, background_tasks: BackgroundTasks,
) -> None:
    if not patient_password_change_limiter.allow(str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="PASSWORD_CHANGE_RATE_LIMITED",
            headers={"Retry-After": str(patient_password_change_limiter.window_seconds)},
        )
    try:
        ProfileService(users, None).change_password(current_user, data)
    except InvalidCurrentPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_CURRENT_PASSWORD",
        ) from error
    email, name = current_user.email, current_user.name
    users.session.commit()
    background_tasks.add_task(send_password_changed_email, email, name)


@router.get("/professionals/me/profile", response_model=ProfessionalProfileResponse)
def get_professional_profile(current_user: CurrentProfessional, profiles: Profiles):
    try:
        return ProfileService(None, profiles).get_professional_profile(current_user)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/professionals/me/profile", response_model=ProfessionalProfileResponse)
def update_professional_profile(
    data: ProfessionalProfileUpdate,
    current_user: CurrentProfessional,
    profiles: Profiles,
    audits: Audits,
    notifications: Annotated[NotificationService, Depends(get_notification_service)] = None,
):
    try:
        return ProfileService(None, profiles).update_professional_profile(current_user, data, audits, notifications)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ProfileChangeValidation as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/professionals/me/notification-settings", response_model=ProfessionalNotificationSettings)
def professional_notification_settings(current_user: CurrentProfessional, profiles: Profiles):
    try:
        return ProfileService(None, profiles).get_professional_profile(current_user)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/professionals/me/notification-settings", response_model=ProfessionalNotificationSettings)
def update_professional_notification_settings(data: ProfessionalNotificationSettings, current_user: CurrentProfessional, profiles: Profiles, audits: Audits):
    try:
        profile = ProfileService(None, profiles).get_professional_profile(current_user)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    profile.email_notifications_enabled = data.email_notifications_enabled
    profiles.session.flush()
    AuditService(audits).record(current_user.id, current_user.role, AuditAction.UPDATE, "professional_notification_settings", profile.id)
    return profile


@router.patch("/professionals/me", response_model=UserResponse)
def update_professional(data: BasicUserUpdate, current_user: CurrentProfessional, users: Users):
    return ProfileService(users, None).update_basic_user(current_user, data)


@router.post("/professionals/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_professional_password(
    data: ChangePasswordRequest,
    current_user: CurrentProfessional,
    users: Users,
) -> None:
    try:
        ProfileService(users, None).change_password(current_user, data)
    except InvalidCurrentPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_CURRENT_PASSWORD",
        ) from error
