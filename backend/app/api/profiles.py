from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_current_patient,
    get_current_professional,
    get_profile_repository,
    get_user_repository,
)
from app.models import User
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
)
from app.services.profile_service import (
    InvalidCurrentPasswordError,
    ProfileNotFoundError,
    ProfileService,
)


router = APIRouter(tags=["profiles"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Users = Annotated[UserRepository, Depends(get_user_repository)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]


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
    try:
        return ProfileService(None, profiles).update_patient_profile(current_user, data)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/patients/me", response_model=UserResponse)
def update_patient(data: BasicUserUpdate, current_user: CurrentPatient, users: Users):
    return ProfileService(users, None).update_basic_user(current_user, data)


@router.post("/patients/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_patient_password(data: ChangePasswordRequest, current_user: CurrentPatient, users: Users) -> None:
    try:
        ProfileService(users, None).change_password(current_user, data)
    except InvalidCurrentPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from error


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
):
    try:
        return ProfileService(None, profiles).update_professional_profile(current_user, data)
    except ProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


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
            detail="Current password is incorrect",
        ) from error