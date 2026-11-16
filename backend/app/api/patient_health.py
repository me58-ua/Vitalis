from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_appointment_repository,
    get_audit_repository,
    get_current_patient,
    get_current_professional,
    DbSession,
    get_family_history_repository,
    get_prescription_repository,
    get_profile_repository,
    get_notification_service,
    get_health_document_repository,
)
from app.models import Allergy, ChronicCondition, HabitLog, HabitType, Medication, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.health import (
    AllergyCreate, AllergyResponse, ChronicConditionCreate, ChronicConditionResponse,
    ConsentUpdate, HabitLogCreate, HabitLogResponse, HealthSnapshot, MedicationCreate,
    MedicationResponse, FamilyHistoryResponse,
)
from app.services.patient_health_service import PatientHealthService
from app.models import AuditAction
from app.services.audit_service import AuditService
from app.services.habit_units import normalize_habit_value
from app.repositories.family_history_repository import FamilyHistoryRepository
from app.repositories.health_document_repository import HealthDocumentRepository
from app.repositories.risk_repository import RiskRepository
from app.repositories.risk_snapshot_repository import RiskSnapshotRepository
from app.services.family_history_service import FamilyHistoryNotFoundError, FamilyHistoryService
from app.services.risk_service import RiskService
from app.services.notification_service import NotificationService


router = APIRouter(tags=["patient-health"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Prescriptions = Annotated[PrescriptionRepository, Depends(get_prescription_repository)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]
FamilyHistory = Annotated[FamilyHistoryRepository, Depends(get_family_history_repository)]
Notifications = Annotated[NotificationService, Depends(get_notification_service)]
HealthDocuments = Annotated[HealthDocumentRepository, Depends(get_health_document_repository)]


def _risk_service(db, notifications=None):
    return RiskService(RiskRepository(db), RiskSnapshotRepository(db), notifications)


def _profile(current_user: User, profiles: ProfileRepository):
    profile = profiles.get_patient(current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="PROFILE_NOT_FOUND")
    return profile


@router.get("/patients/me/health")
def get_my_health(current_user: CurrentPatient, profiles: Profiles):
    return PatientHealthService(profiles).snapshot(_profile(current_user, profiles))


@router.patch("/patients/me/consentimiento")
@router.patch("/patients/{patient_id}/consentimiento")
def update_consent(
    data: ConsentUpdate,
    current_user: CurrentPatient,
    profiles: Profiles,
    audits: Audits,
    patient_id: UUID | None = None,
):
    if patient_id is not None and patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="PATIENT_REQUIRED")
    profile = _profile(current_user, profiles)
    profile.share_health_data = data.share_health_data
    profiles.session.flush()
    AuditService(audits).record(
        current_user.id,
        current_user.role,
        AuditAction.UPDATE,
        "patient_profile",
        profile.id,
        current_user.id,
    )
    return {"share_health_data": profile.share_health_data}


@router.get("/patients/me/family-history", response_model=list[FamilyHistoryResponse])
def list_my_family_history(current_user: CurrentPatient, profiles: Profiles, entries: FamilyHistory):
    try:
        return FamilyHistoryService(entries, profiles).list_for_patient(current_user)
    except FamilyHistoryNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/professionals/patients/{patient_id}/health-snapshot", response_model=HealthSnapshot)
def patient_health_snapshot(
    patient_id: UUID,
    current_user: CurrentProfessional,
    profiles: Profiles,
    appointments: Appointments,
    prescriptions: Prescriptions,
    audits: Audits,
    documents: HealthDocuments,
):
    if not appointments.has_shared_appointment(patient_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="NO_SHARED_APPOINTMENT")
    return PatientHealthService(
        profiles, appointments, prescriptions, audits, health_documents=documents
    ).snapshot_by_user_id(patient_id, current_user.id)
