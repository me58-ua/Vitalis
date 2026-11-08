from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import ValidationError

from app.api.deps import DbSession, get_current_professional, get_current_user, get_audit_repository
from app.models import User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.working_hours_repository import WorkingHoursRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.schemas.working_hours import WorkingHoursCreate, WorkingHoursUpdate, WorkingHoursResponse, ChatAvailabilityResponse
from app.services.working_hours_service import WorkingHoursService, SpontaneousChatAvailabilityService
from app.services.appointment_service import AppointmentConflictError, AppointmentNotFoundError

router = APIRouter(tags=['working-hours'])
Professional = Annotated[User, Depends(get_current_professional)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]


@router.get('/professionals/me/working-hours', response_model=list[WorkingHoursResponse])
def list_working_hours(user: Professional, db: DbSession, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return WorkingHoursRepository(db).list(user.id)


def _save(user, data, db, audits, schedule_id=None):
    try:
        return WorkingHoursService(WorkingHoursRepository(db), audits).save(user, data, schedule_id)
    except AppointmentNotFoundError as error: raise HTTPException(404, str(error)) from error
    except AppointmentConflictError as error: raise HTTPException(409, str(error)) from error
    except ValidationError as error: raise HTTPException(422, 'SCHEDULE_INVALID_RANGE_OR_SLOT') from error


@router.post('/professionals/me/working-hours', response_model=WorkingHoursResponse, status_code=201)
def create_working_hours(data: WorkingHoursCreate, user: Professional, db: DbSession, audits: Audits):
    return _save(user, data, db, audits)


@router.patch('/professionals/me/working-hours/{schedule_id}', response_model=WorkingHoursResponse)
def update_working_hours(schedule_id: UUID, data: WorkingHoursUpdate, user: Professional, db: DbSession, audits: Audits):
    return _save(user, data, db, audits, schedule_id)


@router.delete('/professionals/me/working-hours/{schedule_id}', status_code=204)
def delete_working_hours(schedule_id: UUID, user: Professional, db: DbSession, audits: Audits):
    try: WorkingHoursService(WorkingHoursRepository(db), audits).delete(user, schedule_id)
    except AppointmentNotFoundError as error: raise HTTPException(404, str(error)) from error


@router.get('/professionals/{professional_id}/chat-availability', response_model=ChatAvailabilityResponse)
def chat_availability(professional_id: UUID, user: CurrentUser, db: DbSession, response: Response):
    if user.role not in (UserRole.PATIENT, UserRole.PROFESSIONAL): raise HTTPException(403, 'CHAT_ROLE_REQUIRED')
    response.headers['Cache-Control'] = 'no-store'
    return SpontaneousChatAvailabilityService(WorkingHoursRepository(db), ProfessionalRepository(db)).get(professional_id)
