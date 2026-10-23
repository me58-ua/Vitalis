from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DbSession, get_appointment_repository, get_audit_repository,
    get_current_patient, get_current_professional, get_profile_repository,
)
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.risk_snapshot_repository import RiskSnapshotRepository
from app.schemas.risk import RiskHistoryResponse
from app.services.risk_history_service import RiskHistoryAccessError, RiskHistoryService


router = APIRouter(tags=["risk"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
CurrentProfessional = Annotated[User, Depends(get_current_professional)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]


def _history(
    patient_id: UUID, current_user: User, db, profiles, appointments, audits,
    model, from_date, to_date, cursor, limit,
):
    try:
        return RiskHistoryService(
            RiskSnapshotRepository(db), profiles, appointments, audits
        ).list_for_user(patient_id, current_user, model, from_date, to_date, cursor, limit)
    except RiskHistoryAccessError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.get("/patients/{patient_id}/risk-history", response_model=RiskHistoryResponse)
def patient_risk_history(
    patient_id: UUID,
    current_user: CurrentPatient,
    db: DbSession,
    profiles: Profiles,
    appointments: Appointments,
    audits: Audits,
    model: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    return _history(patient_id, current_user, db, profiles, appointments, audits, model, from_date, to_date, cursor, limit)


@router.get("/professionals/patients/{patient_id}/risk-history", response_model=RiskHistoryResponse)
def professional_risk_history(
    patient_id: UUID,
    current_user: CurrentProfessional,
    db: DbSession,
    profiles: Profiles,
    appointments: Appointments,
    audits: Audits,
    model: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    return _history(patient_id, current_user, db, profiles, appointments, audits, model, from_date, to_date, cursor, limit)
