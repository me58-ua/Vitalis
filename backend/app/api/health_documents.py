from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import (
    get_appointment_repository,
    get_current_patient,
    get_current_professional,
    get_file_storage,
    get_health_document_repository,
    get_profile_repository,
)
from app.config import settings
from app.models import HealthDocumentType, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.health_document_repository import HealthDocumentRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.health_documents import HealthDocumentListResponse, HealthDocumentResponse
from app.services.file_storage import FileStorage
from app.services.health_document_service import (
    HealthDocumentAccessError,
    HealthDocumentNotFoundError,
    HealthDocumentService,
    HealthDocumentValidationError,
)


router = APIRouter(tags=["health-documents"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Documents = Annotated[HealthDocumentRepository, Depends(get_health_document_repository)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]


def _service(documents, profiles, appointments, storage):
    return HealthDocumentService(
        documents, profiles, appointments, storage, settings.HEALTH_DOCUMENT_MAX_SIZE_BYTES
    )


@router.post("/patients/me/health/documents", response_model=HealthDocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_health_document(
    current_user: CurrentPatient,
    documents: Documents,
    profiles: Profiles,
    appointments: Appointments,
    storage: Storage,
    tipo: HealthDocumentType = Form(...),
    descripcion: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    try:
        return _service(documents, profiles, appointments, storage).upload(
            current_user, file.file, file.filename or "health-document", file.content_type, tipo, descripcion
        )
    except HealthDocumentValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.get("/patients/me/health/documents", response_model=HealthDocumentListResponse)
def list_my_health_documents(current_user: CurrentPatient, documents: Documents, profiles: Profiles, appointments: Appointments, storage: Storage):
    try:
        items = _service(documents, profiles, appointments, storage).list_for_patient(current_user)
        return {"documents": items, "total": len(items)}
    except HealthDocumentValidationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/patients/me/health/documents/{document_id}")
def download_my_health_document(document_id: UUID, current_user: CurrentPatient, documents: Documents, profiles: Profiles, appointments: Appointments, storage: Storage):
    try:
        document, path = _service(documents, profiles, appointments, storage).download_for_patient(document_id, current_user)
        return FileResponse(path, filename=Path(document.file_url).name)
    except HealthDocumentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except HealthDocumentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/professionals/{professional_id}/patients/{patient_id}/health/documents", response_model=HealthDocumentListResponse)
def list_patient_health_documents(professional_id: UUID, patient_id: UUID, current_user: CurrentProfessional, documents: Documents, profiles: Profiles, appointments: Appointments, storage: Storage):
    if professional_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PROFESSIONAL_IDENTITY_MISMATCH")
    try:
        items = _service(documents, profiles, appointments, storage).list_for_professional(patient_id, current_user.id)
        return {"documents": items, "total": len(items)}
    except HealthDocumentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except HealthDocumentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/professionals/{professional_id}/patients/{patient_id}/health/documents/{document_id}")
def download_patient_health_document(professional_id: UUID, patient_id: UUID, document_id: UUID, current_user: CurrentProfessional, documents: Documents, profiles: Profiles, appointments: Appointments, storage: Storage):
    if professional_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PROFESSIONAL_IDENTITY_MISMATCH")
    try:
        document, path = _service(documents, profiles, appointments, storage).download_for_professional(
            document_id, patient_id, current_user.id
        )
        return FileResponse(path, filename=Path(document.file_url).name)
    except HealthDocumentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except HealthDocumentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error