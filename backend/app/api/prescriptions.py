from datetime import date, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api.deps import (
    get_appointment_repository,
    get_audit_repository,
    get_current_admin,
    get_current_patient,
    get_current_professional,
    get_file_storage,
    get_prescription_repository,
    get_profile_repository,
)
from app.config import settings
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.prescriptions import (
    PrescriptionAuthorizationCreate,
    PrescriptionAuthorizationResponse,
    PatientPrescriptionListResponse,
    PrescriptionResponse,
    PrescriptionListResponse,
    PrescriptionMetadata,
    PrescriptionType,
)
from app.services.file_storage import FileStorage
from app.services.prescription_service import (
    PrescriptionAccessError,
    PrescriptionConflictError,
    PrescriptionNotFoundError,
    PrescriptionService,
    PrescriptionValidationError,
)
from app.services.professional_follow_up_service import ProfessionalFollowUpService
from app.services.appointment_service import AppointmentAccessError


router = APIRouter(tags=["prescriptions"])
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Prescriptions = Annotated[PrescriptionRepository, Depends(get_prescription_repository)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]


def _service(
    appointments: AppointmentRepository,
    profiles: ProfileRepository,
    prescriptions: PrescriptionRepository,
    storage: FileStorage,
    audits: AuditRepository | None = None,
) -> PrescriptionService:
    return PrescriptionService(
        appointments,
        profiles,
        prescriptions,
        storage,
        emission_window=timedelta(hours=settings.PRESCRIPTION_EMISSION_WINDOW_HOURS),
        max_file_size=settings.PRESCRIPTION_MAX_SIZE_BYTES,
        audits=audits,
    )


@router.post(
    "/professionals/{professional_id}/appointments/{appointment_id}/prescription",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_prescription(
    professional_id: UUID,
    appointment_id: UUID,
    current_user: CurrentProfessional,
    appointments: Appointments,
    profiles: Profiles,
    prescriptions: Prescriptions,
    storage: Storage,
    audits: Audits,
    file: UploadFile = File(...),
    tipo: PrescriptionType = Form(...),
    titulo: str = Form(..., min_length=1, max_length=300),
    fecha_emision: date = Form(...),
    fecha_caducidad: date | None = Form(default=None),
    codigo: str | None = Form(default=None, max_length=100),
    notas: str | None = Form(default=None),
):
    try:
        metadata = PrescriptionMetadata(tipo=tipo, titulo=titulo, fecha_emision=fecha_emision,
                                        fecha_caducidad=fecha_caducidad, codigo=codigo)
        return _service(appointments, profiles, prescriptions, storage, audits).upload(
            professional_id,
            current_user,
            appointment_id,
            file.file,
            file.filename or "prescription",
            file.content_type,
            notas,
            metadata=metadata,
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()[0]["msg"]) from error
    except PrescriptionAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except PrescriptionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except PrescriptionValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except PrescriptionConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/admin/appointments/{appointment_id}/prescription-authorization",
    response_model=PrescriptionAuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def authorize_late_prescription(
    appointment_id: UUID,
    data: PrescriptionAuthorizationCreate,
    current_admin: CurrentAdmin,
    appointments: Appointments,
    profiles: Profiles,
    prescriptions: Prescriptions,
    storage: Storage,
    audits: Audits,
):
    try:
        return _service(appointments, profiles, prescriptions, storage, audits).authorize_late_issue(
            appointment_id, current_admin, data
        )
    except PrescriptionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except PrescriptionValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except PrescriptionConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/patients/me/appointments/{appointment_id}/prescription")
def download_prescription(
    appointment_id: UUID,
    current_user: CurrentPatient,
    appointments: Appointments,
    profiles: Profiles,
    prescriptions: Prescriptions,
    storage: Storage,
):
    try:
        prescription, path = _service(appointments, profiles, prescriptions, storage).download_for_patient(
            appointment_id, current_user
        )
        return FileResponse(path, filename=Path(prescription.file_url).name, headers={"Cache-Control": "no-store"})
    except PrescriptionAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except PrescriptionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/professionals/{professional_id}/appointments/{appointment_id}/prescription")
def download_professional_prescription(
    professional_id: UUID, appointment_id: UUID, current_user: CurrentProfessional,
    appointments: Appointments, profiles: Profiles, prescriptions: Prescriptions, storage: Storage,
):
    try:
        prescription, path = _service(appointments, profiles, prescriptions, storage).download_for_professional(
            professional_id, appointment_id, current_user,
        )
        return FileResponse(path, filename=Path(prescription.file_url).name, headers={"Cache-Control": "no-store"})
    except PrescriptionAccessError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except PrescriptionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get(
    "/patients/{patient_id}/prescriptions",
    response_model=PatientPrescriptionListResponse,
)
def list_patient_prescriptions(
    patient_id: UUID,
    current_user: CurrentPatient,
    profiles: Profiles,
    prescriptions: Prescriptions,
    appointments: Appointments,
    storage: Storage,
    professional_id: UUID | None = None,
):
    try:
        items = _service(appointments, profiles, prescriptions, storage).list_for_patient_view(
            patient_id, current_user, professional_id
        )
        return {"prescriptions": items, "total": len(items)}
    except PrescriptionAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except PrescriptionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/professionals/{professional_id}/prescriptions",
    response_model=PrescriptionListResponse,
)
def list_professional_prescriptions(
    professional_id: UUID,
    current_user: CurrentProfessional,
    appointments: Appointments,
    profiles: Profiles,
    prescriptions: Prescriptions,
    patient_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    try:
        return ProfessionalFollowUpService(appointments, prescriptions, profiles).list_prescriptions(
            professional_id,
            current_user,
            patient_id,
            start_date,
            end_date,
            page,
            page_size,
        )
    except AppointmentAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
