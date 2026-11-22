from datetime import date, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from app.api.deps import (
    get_appointment_repository,
    get_audit_repository,
    get_current_admin,
    get_current_patient,
    get_current_professional,
    get_file_storage,
    get_notification_repository,
    get_prescription_repository,
    get_profile_repository,
)
from app.config import settings
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.prescriptions import (
    LatePrescriptionRequestResponse,
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
    PrescriptionWindowExpiredError,
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
Notifications = Annotated[NotificationRepository, Depends(get_notification_repository)]


def _service(
    appointments: AppointmentRepository,
    profiles: ProfileRepository,
    prescriptions: PrescriptionRepository,
    storage: FileStorage,
    audits: AuditRepository | None = None,
    notifications: NotificationRepository | None = None,
) -> PrescriptionService:
    return PrescriptionService(
        appointments,
        profiles,
        prescriptions,
        storage,
        emission_window=timedelta(hours=settings.PRESCRIPTION_EMISSION_WINDOW_HOURS),
        max_file_size=settings.PRESCRIPTION_MAX_SIZE_BYTES,
        audits=audits,
        notifications=notifications,
    )


@router.post(
    "/professionals/{professional_id}/appointments/{appointment_id}/prescription",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={202: {"model": LatePrescriptionRequestResponse}},
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
    notifications: Notifications,
    file: UploadFile = File(...),
    tipo: PrescriptionType = Form(...),
    titulo: str = Form(..., min_length=1, max_length=300),
    fecha_emision: date = Form(...),
    fecha_caducidad: date | None = Form(default=None),
    notas: str | None = Form(default=None),
    late_reason: str | None = Form(default=None, max_length=1000),
):
    try:
        metadata = PrescriptionMetadata(tipo=tipo, titulo=titulo, fecha_emision=fecha_emision,
                                        fecha_caducidad=fecha_caducidad)
        result = _service(appointments, profiles, prescriptions, storage, audits, notifications).upload(
            professional_id,
            current_user,
            appointment_id,
            file.file,
            file.filename or "prescription",
            file.content_type,
            notas,
            metadata=metadata,
            late_reason=late_reason,
        )
        if late_reason is not None:
            return JSONResponse(status_code=202, content=LatePrescriptionRequestResponse.model_validate(
                result
            ).model_dump(mode="json"))
        return result
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()[0]["msg"]) from error
    except PrescriptionWindowExpiredError as error:
        raise HTTPException(status_code=403, detail="PRESCRIPTION_WINDOW_EXPIRED") from error
    except PrescriptionAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except PrescriptionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except PrescriptionValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except PrescriptionConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/admin/late-prescription-requests/{request_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
)
def authorize_late_prescription(
    request_id: UUID,
    current_admin: CurrentAdmin,
    appointments: Appointments,
    profiles: Profiles,
    prescriptions: Prescriptions,
    storage: Storage,
    audits: Audits,
    notifications: Notifications,
):
    try:
        _service(appointments, profiles, prescriptions, storage, audits, notifications).authorize_late_issue(
            request_id, current_admin
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
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
