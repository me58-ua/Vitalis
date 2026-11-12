import asyncio
from collections import deque
from datetime import timedelta
from time import monotonic
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.config import settings
from app.core.security import decode_access_token
from app.database import SessionLocal
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.user_repository import UserRepository
from app.repositories.notification_repository import NotificationRepository
from app.services.auth_service import AuthService, InvalidAccessTokenError
from app.services.chat_service import ChatForbiddenError, ChatNotFoundError, ChatService, ChatValidationError
from app.services.connection_manager import ConnectionManager
from app.services.notification_service import NotificationService

router = APIRouter(tags=["chat-websocket"])
manager = ConnectionManager()


def _authenticate(token: str):
    with SessionLocal() as db:
        return AuthService(UserRepository(db)).get_current_user(token)


@router.websocket("/ws/chat/{appointment_id}")
async def chat_websocket(websocket: WebSocket, appointment_id: UUID):
    """Chat socket; after reconnecting, recover missed messages with REST `after_id`."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    try:
        user = _authenticate(token)
    except (InvalidAccessTokenError, JWTError, ValueError):
        await websocket.close(code=4401)
        return

    access_db = SessionLocal()
    try:
        service = ChatService(
            AppointmentRepository(access_db),
            ChatMessageRepository(access_db),
            timedelta(hours=settings.CHAT_WRITE_WINDOW_HOURS),
            settings.CHAT_MESSAGE_MAX_LENGTH,
        )
        try:
            service.get_room_access(appointment_id, user)
        except ChatNotFoundError:
            await websocket.close(code=4404)
            return
        except ChatForbiddenError:
            await websocket.close(code=4403)
            return

        await manager.connect(appointment_id, websocket)
        access_db.close()
        sent_times = deque()
        last_typing = 0.0
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=settings.CHAT_CONNECTION_IDLE_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    await websocket.close(code=1000)
                    return
                if not isinstance(payload, dict):
                    await websocket.send_json({"type": "error", "code": "INVALID_PAYLOAD"})
                    continue
                message_type = payload.get("type")
                try:
                    user = _authenticate(token)
                except (InvalidAccessTokenError, JWTError, ValueError):
                    await websocket.close(code=4401)
                    return
                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                if message_type == "typing":
                    now = monotonic()
                    if now - last_typing < 0.5:
                        continue
                    with SessionLocal() as typing_db:
                        typing_service = ChatService(AppointmentRepository(typing_db))
                        try:
                            appointment = typing_service.get_room_access(appointment_id, user)
                            if not typing_service.can_write(appointment):
                                continue
                        except (ChatNotFoundError, ChatForbiddenError):
                            await websocket.close(code=4403)
                            return
                    last_typing = now
                    await manager.broadcast(appointment_id, {"type": "typing", "sender_id": str(user.id),
                                                            "is_typing": payload.get("is_typing") is True})
                    continue
                if message_type != "message":
                    await websocket.send_json({"type": "error", "code": "UNSUPPORTED_MESSAGE_TYPE"})
                    continue
                now = monotonic()
                while sent_times and now - sent_times[0] >= settings.CHAT_RATE_LIMIT_WINDOW_SECONDS:
                    sent_times.popleft()
                if len(sent_times) >= settings.CHAT_RATE_LIMIT_MESSAGES:
                    await websocket.send_json({"type": "error", "code": "MESSAGE_RATE_LIMITED"})
                    continue
                try:
                    message_db = SessionLocal()
                    try:
                        message = ChatService(
                            AppointmentRepository(message_db),
                            ChatMessageRepository(message_db),
                            timedelta(hours=settings.CHAT_WRITE_WINDOW_HOURS),
                            settings.CHAT_MESSAGE_MAX_LENGTH,
                            NotificationService(NotificationRepository(message_db)),
                        ).save_message(appointment_id, user, str(payload.get("content", "")))
                        message_db.commit()
                    finally:
                        message_db.close()
                except (ChatForbiddenError, ChatValidationError) as error:
                    code = (
                        "CHAT_MESSAGE_INVALID"
                        if isinstance(error, ChatValidationError)
                        else "CHAT_FORBIDDEN"
                    )
                    await websocket.send_json({"type": "error", "code": code})
                    continue
                sent_times.append(now)
                await manager.broadcast(
                    appointment_id,
                    {
                        "type": "message",
                        "id": str(message.id),
                        "sender_id": str(message.sender_id),
                        "content": message.content,
                        "created_at": message.sent_at.isoformat(),
                    },
                )
        except WebSocketDisconnect:
            return
    finally:
        manager.disconnect(appointment_id, websocket)
        access_db.close()


@router.websocket("/ws/spontaneous-chat/{chat_id}")
async def spontaneous_websocket(websocket: WebSocket, chat_id: UUID):
    from app.api.spontaneous_chat import service
    from app.services.spontaneous_chat_service import SpontaneousChatError
    from app.services.spontaneous_connections import manager as spontaneous_manager

    token = websocket.query_params.get("token")
    try:
        if not token:
            raise InvalidAccessTokenError()
        user = _authenticate(token)
        with SessionLocal() as db:
            service(db).owned(chat_id, user)
    except (InvalidAccessTokenError, JWTError, ValueError):
        await websocket.close(code=4401)
        return
    except SpontaneousChatError:
        await websocket.close(code=4403)
        return
    await spontaneous_manager.connect(chat_id, websocket)
    last_typing = 0.0
    try:
        while True:
            payload = await asyncio.wait_for(websocket.receive_json(), timeout=settings.CHAT_CONNECTION_IDLE_TIMEOUT_SECONDS)
            try:
                user = _authenticate(token)
                with SessionLocal() as db:
                    current = service(db)
                    room = current.owned(chat_id, user)
                    writable = room.status == 'open' and current.availability.get(room.professional_id)['available']
            except (InvalidAccessTokenError, JWTError, ValueError, SpontaneousChatError):
                await websocket.close(code=4403)
                return
            if not isinstance(payload, dict):
                continue
            if payload.get('type') == 'ping':
                await websocket.send_json({'type': 'pong'})
            elif payload.get('type') == 'typing' and writable and monotonic() - last_typing >= 0.5:
                last_typing = monotonic()
                await spontaneous_manager.broadcast(chat_id, {'type': 'typing', 'sender_id': str(user.id),
                                                              'is_typing': payload.get('is_typing') is True})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        spontaneous_manager.disconnect(chat_id, websocket)
