from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_chat_message_repository,
    get_current_user,
    get_appointment_repository,
    get_notification_service,
)
from app.config import settings
from app.models import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.schemas.chat import (
    ChatInboxResponse,
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatParticipant,
    ChatRoomResponse,
)
from app.services.chat_service import (
    ChatForbiddenError,
    ChatNotFoundError,
    ChatService,
    ChatValidationError,
)
from app.services.notification_service import NotificationService

router = APIRouter(tags=["chat"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Appointments = Annotated[AppointmentRepository, Depends(get_appointment_repository)]
Messages = Annotated[ChatMessageRepository, Depends(get_chat_message_repository)]
Notifications = Annotated[NotificationService, Depends(get_notification_service)]


@router.get("/chats/appointments", response_model=ChatInboxResponse)
def list_appointment_chats(user: CurrentUser, appointments: Appointments,
                           page: int = Query(default=1, ge=1),
                           page_size: int = Query(default=20, ge=1, le=100)):
    if user.role.value not in ("patient", "professional"):
        raise HTTPException(status_code=403, detail="Chat is for appointment participants only")
    rows, total = appointments.list_chat_rooms(user.id, (page - 1) * page_size, page_size)
    return ChatInboxResponse(chats=rows, total=total, page=page, page_size=page_size)


def get_chat_service(
    appointments: Appointments, messages: Messages, notifications: Notifications
) -> ChatService:
    return ChatService(
        appointments,
        messages,
        timedelta(hours=settings.CHAT_WRITE_WINDOW_HOURS),
        settings.CHAT_MESSAGE_MAX_LENGTH,
        notifications,
    )


def _message_response(message) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        appointment_id=message.appointment_id,
        sender_id=message.sender_id,
        content=message.content,
        created_at=message.sent_at,
    )


def _translate(error: Exception) -> HTTPException:
    if isinstance(error, ChatNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ChatForbiddenError):
        return HTTPException(status_code=403, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("/appointments/{appointment_id}/chat", response_model=ChatRoomResponse)
def get_chat_room(
    appointment_id: UUID,
    user: CurrentUser,
    service: Annotated[ChatService, Depends(get_chat_service)],
):
    try:
        appointment = service.get_room_access(appointment_id, user)
        return ChatRoomResponse(
            appointment_id=appointment.id,
            participants=[
                ChatParticipant(id=appointment.patient_id, role="patient"),
                ChatParticipant(id=appointment.professional_id, role="professional"),
            ],
            can_write=service.can_write(appointment),
            status=appointment.status,
        )
    except (ChatNotFoundError, ChatForbiddenError) as error:
        raise _translate(error) from error


@router.get("/appointments/{appointment_id}/chat/messages", response_model=ChatMessageListResponse)
def list_chat_messages(
    appointment_id: UUID,
    user: CurrentUser,
    service: Annotated[ChatService, Depends(get_chat_service)],
    limit: int = Query(default=50, ge=1, le=100),
    before_id: UUID | None = None,
    after_id: UUID | None = None,
):
    try:
        messages = service.list_messages(appointment_id, user, limit, before_id, after_id)
        return ChatMessageListResponse(messages=[_message_response(message) for message in messages])
    except (ChatNotFoundError, ChatForbiddenError) as error:
        raise _translate(error) from error


@router.post(
    "/appointments/{appointment_id}/chat/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chat_message(
    appointment_id: UUID,
    data: ChatMessageCreate,
    user: CurrentUser,
    service: Annotated[ChatService, Depends(get_chat_service)],
):
    try:
        return _message_response(service.save_message(appointment_id, user, data.content))
    except (ChatNotFoundError, ChatForbiddenError, ChatValidationError) as error:
        raise _translate(error) from error
