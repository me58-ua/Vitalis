from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import DbSession, get_current_user, get_audit_repository, get_file_storage
from app.models import User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.working_hours_repository import WorkingHoursRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.spontaneous_chat_repository import SpontaneousChatRepository
from app.services.file_storage import FileStorage
from app.services.working_hours_service import SpontaneousChatAvailabilityService
from app.services.spontaneous_chat_service import SpontaneousChatService, SpontaneousChatError
from app.schemas.spontaneous_chat import StartSpontaneousChat, SpontaneousChatResponse, SpontaneousChatPage, SpontaneousMessageResponse, SpontaneousMessagePage
from app.core.rate_limit import InMemoryRateLimiter
from app.services.spontaneous_connections import manager

router = APIRouter(prefix='/spontaneous-chats', tags=['spontaneous-chat'])
Current = Annotated[User, Depends(get_current_user)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]
limiter = InMemoryRateLimiter(10, 5)


def service(db, storage=None, audits=None):
    hours = WorkingHoursRepository(db)
    return SpontaneousChatService(SpontaneousChatRepository(db), hours,
        SpontaneousChatAvailabilityService(hours, ProfessionalRepository(db)), storage, audits)


def translate(operation):
    try: return operation()
    except SpontaneousChatError as error: raise HTTPException(error.status, error.code) from error
    except ValueError as error: raise HTTPException(422, 'CHAT_CURSOR_INVALID') from error


@router.get('', response_model=SpontaneousChatPage)
def list_chats(user: Current, db: DbSession, response: Response, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    if user.role not in (UserRole.PATIENT, UserRole.PROFESSIONAL): raise HTTPException(403, 'CHAT_ROLE_REQUIRED')
    response.headers['Cache-Control'] = 'no-store'
    chat_service = service(db)
    rows, total = chat_service.repository.list(user.id, (page - 1) * page_size, page_size)
    return dict(chats=[chat_service.response(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post('', response_model=SpontaneousChatResponse, status_code=201)
def start_chat(data: StartSpontaneousChat, user: Current, db: DbSession, audits: Audits):
    chat_service = service(db, audits=audits)
    return translate(lambda: chat_service.response(chat_service.start(user, data.professional_id)))


@router.get('/{chat_id}', response_model=SpontaneousChatResponse)
def get_chat(chat_id: UUID, user: Current, db: DbSession, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    chat_service = service(db)
    return translate(lambda: chat_service.response(chat_service.owned(chat_id, user)))


@router.post('/{chat_id}/close', response_model=SpontaneousChatResponse)
async def close_chat(chat_id: UUID, user: Current, db: DbSession, audits: Audits):
    chat_service = service(db, audits=audits)
    result = translate(lambda: chat_service.response(chat_service.close(chat_id, user)))
    db.commit()
    await manager.broadcast(chat_id, {"type": "changed"})
    return result


@router.get('/{chat_id}/messages', response_model=SpontaneousMessagePage)
def messages(chat_id: UUID, user: Current, db: DbSession, response: Response, limit: int = Query(50, ge=1, le=100), before_id: UUID | None = None, after_id: UUID | None = None):
    if before_id and after_id: raise HTTPException(422, 'CHAT_CURSOR_INVALID')
    response.headers['Cache-Control'] = 'no-store'
    chat_service = service(db)
    translate(lambda: chat_service.owned(chat_id, user))
    rows, more = translate(lambda: chat_service.repository.messages(chat_id, limit, before_id, after_id))
    return dict(messages=rows, has_more=more)


@router.post('/{chat_id}/messages', response_model=SpontaneousMessageResponse, status_code=201)
async def send_message(chat_id: UUID, user: Current, db: DbSession, storage: Storage, audits: Audits,
                 client_id: UUID = Form(...), content: str = Form('', max_length=2000), file: UploadFile | None = File(None)):
    if not limiter.allow(f'{user.id}:{chat_id}'): raise HTTPException(429, 'CHAT_RATE_LIMITED')
    message = translate(lambda: service(db, storage, audits).send(chat_id, user, client_id, content, file))
    result = SpontaneousMessageResponse.model_validate(message)
    db.commit()
    await manager.broadcast(chat_id, {"type": "changed"})
    return result


@router.get('/{chat_id}/messages/{message_id}/file')
def download_attachment(chat_id: UUID, message_id: UUID, user: Current, db: DbSession, storage: Storage, audits: Audits):
    message, path = translate(lambda: service(db, storage, audits).download(chat_id, message_id, user))
    return FileResponse(path, filename=message.file_name, media_type=message.content_type,
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
