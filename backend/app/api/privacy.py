from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_audit_repository,
    get_current_patient,
    get_current_professional,
    get_file_storage,
    get_privacy_repository,
    get_profile_repository,
)
from app.models import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.privacy_repository import PrivacyRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.file_storage import FileStorage
from app.services.privacy_service import PrivacyAccountNotFoundError, PrivacyService


router = APIRouter(tags=["privacy"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Privacy = Annotated[PrivacyRepository, Depends(get_privacy_repository)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]


def _erase(current_user: User, privacy: PrivacyRepository, profiles: ProfileRepository, audits: AuditRepository, storage: FileStorage):
    try:
        PrivacyService(privacy, profiles, audits, storage).erase_account(current_user)
    except PrivacyAccountNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/patients/me/account", status_code=status.HTTP_204_NO_CONTENT)
def erase_patient_account(current_user: CurrentPatient, privacy: Privacy, profiles: Profiles, audits: Audits, storage: Storage) -> None:
    _erase(current_user, privacy, profiles, audits, storage)


@router.delete("/professionals/me/account", status_code=status.HTTP_204_NO_CONTENT)
def erase_professional_account(current_user: CurrentProfessional, privacy: Privacy, profiles: Profiles, audits: Audits, storage: Storage) -> None:
    _erase(current_user, privacy, profiles, audits, storage)