from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_appointment_repository,
    get_audit_repository,
    get_current_patient,
    get_current_professional,
    get_prescription_repository,
    get_profile_repository,
)
from app.models import Allergy, ChronicCondition, HabitLog, Medication, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.health import (
    AllergyCreate, AllergyResponse, ChronicConditionCreate, ChronicConditionResponse,
    ConsentUpdate, HabitLogCreate, HabitLogResponse, HealthSnapshot, MedicationCreate,
    MedicationResponse, OnboardingMessageRequest, OnboardingMessageResponse, OnboardingSkipResponse,
)
from app.services.patient_health_service import PatientHealthService
from app.models import AuditAction
from app.services.audit_service import AuditService


router = APIRouter(tags=["patient-health"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Prescriptions = Annotated[PrescriptionRepository, Depends(get_prescription_repository)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]


def _profile(current_user: User, profiles: ProfileRepository):
    profile = profiles.get_patient(current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
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
        raise HTTPException(status_code=403, detail="Only the patient can update this consent")
    profile = _profile(current_user, profiles)
    profile.share_health_data = data.share_health_data
    profiles.session.flush()
    AuditService(audits).record(
        current_user.id,
        current_user.role,
        AuditAction.UPDATE,
        "patient_profile",
        profile.id,
        profile.id,
    )
    return {"share_health_data": profile.share_health_data}


@router.post("/patients/me/health/allergies", response_model=AllergyResponse, status_code=201)
def add_allergy(data: AllergyCreate, current_user: CurrentPatient, profiles: Profiles):
    return profiles.add_health_record(Allergy(patient_id=_profile(current_user, profiles).id, **data.model_dump()))


@router.post("/patients/me/health/chronic-conditions", response_model=ChronicConditionResponse, status_code=201)
def add_chronic_condition(data: ChronicConditionCreate, current_user: CurrentPatient, profiles: Profiles):
    return profiles.add_health_record(ChronicCondition(patient_id=_profile(current_user, profiles).id, **data.model_dump()))


@router.post("/patients/me/health/medications", response_model=MedicationResponse, status_code=201)
def add_medication(data: MedicationCreate, current_user: CurrentPatient, profiles: Profiles):
    return profiles.add_health_record(Medication(patient_id=_profile(current_user, profiles).id, **data.model_dump()))


@router.post("/patients/me/health/habits", response_model=HabitLogResponse, status_code=201)
def add_habit(data: HabitLogCreate, current_user: CurrentPatient, profiles: Profiles):
    return profiles.add_health_record(HabitLog(patient_id=_profile(current_user, profiles).id, **data.model_dump()))


@router.post("/onboarding/message", response_model=OnboardingMessageResponse)
def onboarding_message(data: OnboardingMessageRequest, current_user: CurrentPatient, profiles: Profiles):
    profile = _profile(current_user, profiles)
    completed, saved, next_question = PatientHealthService(profiles).save_onboarding_message(profile, data.block, data.message)
    return OnboardingMessageResponse(block=data.block, next_question=next_question, saved=saved, onboarding_completed=completed)


@router.post("/onboarding/skip", response_model=OnboardingSkipResponse)
def skip_onboarding(current_user: CurrentPatient, profiles: Profiles):
    profile = _profile(current_user, profiles)
    return OnboardingSkipResponse(onboarding_completed=PatientHealthService(profiles).skip(profile))


@router.post("/onboarding/resume", response_model=OnboardingSkipResponse)
def resume_onboarding(current_user: CurrentPatient, profiles: Profiles):
    profile = _profile(current_user, profiles)
    profile.onboarding_completed = False
    profiles.session.flush()
    return OnboardingSkipResponse(onboarding_completed=False)


@router.get("/professionals/patients/{patient_id}/health-snapshot", response_model=HealthSnapshot)
def patient_health_snapshot(
    patient_id: UUID,
    current_user: CurrentProfessional,
    profiles: Profiles,
    appointments: Appointments,
    prescriptions: Prescriptions,
    audits: Audits,
):
    if not appointments.has_shared_appointment(patient_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No shared appointment with this patient")
    return PatientHealthService(profiles, appointments, prescriptions, audits).snapshot_by_user_id(
        patient_id, current_user.id
    )