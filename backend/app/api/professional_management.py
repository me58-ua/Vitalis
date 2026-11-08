from datetime import date, datetime, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select

from app.api.deps import DbSession, get_current_professional, get_current_admin, get_audit_repository, get_profile_repository
from app.models import ProfessionalProfile, User
from app.repositories.audit_repository import AuditRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.time_block_repository import TimeBlockRepository
from app.schemas.profiles import ProfessionalProfileResponse
from app.schemas.professional_management import TimeBlockCreate, TimeBlockResponse, ProfileChangeDecision
from app.services.time_block_service import TimeBlockService
from app.services.profile_change_service import ProfileChangeService, ProfileChangeConflict, ProfileChangeValidation
from app.services.profile_service import ProfileNotFoundError
from app.services.appointment_service import AppointmentConflictError, AppointmentNotFoundError

router = APIRouter(tags=["professional-management"])
Professional = Annotated[User, Depends(get_current_professional)]
Admin = Annotated[User, Depends(get_current_admin)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]


@router.get("/professionals/me/time-blocks", response_model=list[TimeBlockResponse])
def list_time_blocks(user: Professional, db: DbSession, response: Response,
                     from_date: date = Query(), to_date: date = Query()):
    if to_date < from_date or (to_date - from_date).days > 366:
        raise HTTPException(422, "TIME_BLOCK_DATE_RANGE")
    zone = ZoneInfo("Europe/Madrid")
    response.headers["Cache-Control"] = "no-store"
    return TimeBlockRepository(db).list(user.id, datetime.combine(from_date, time.min, zone),
                                       datetime.combine(to_date + timedelta(days=1), time.min, zone))


@router.post("/professionals/me/time-blocks", response_model=TimeBlockResponse, status_code=201)
def create_time_block(data: TimeBlockCreate, user: Professional, db: DbSession, audits: Audits):
    try:
        return TimeBlockService(TimeBlockRepository(db), audits).create(user, data)
    except AppointmentConflictError as error:
        raise HTTPException(409, str(error)) from error


@router.delete("/professionals/me/time-blocks/{block_id}", status_code=204)
def delete_time_block(block_id: UUID, user: Professional, db: DbSession, audits: Audits):
    try:
        TimeBlockService(TimeBlockRepository(db), audits).delete(user, block_id)
    except AppointmentNotFoundError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/admin/professionals/profile-changes", response_model=list[ProfessionalProfileResponse])
def pending_profile_changes(_: Admin, db: DbSession, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(select(ProfessionalProfile).where(ProfessionalProfile.change_status == "pending")
                           .order_by(ProfessionalProfile.change_requested_at)))


def _decide(professional_id, data, admin, profiles, audits, approve):
    try:
        return ProfileChangeService(profiles, audits).decide(professional_id, admin, data, approve)
    except ProfileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ProfileChangeConflict as error:
        raise HTTPException(409, str(error)) from error
    except ProfileChangeValidation as error:
        raise HTTPException(422, str(error)) from error


@router.post("/admin/professionals/{professional_id}/profile-change/approve", response_model=ProfessionalProfileResponse)
def approve_profile_change(professional_id: UUID, data: ProfileChangeDecision, admin: Admin, profiles: Profiles, audits: Audits):
    return _decide(professional_id, data, admin, profiles, audits, True)


@router.post("/admin/professionals/{professional_id}/profile-change/reject", response_model=ProfessionalProfileResponse)
def reject_profile_change(professional_id: UUID, data: ProfileChangeDecision, admin: Admin, profiles: Profiles, audits: Audits):
    return _decide(professional_id, data, admin, profiles, audits, False)
