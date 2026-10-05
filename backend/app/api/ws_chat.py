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
                message_type = payload.get("type")
                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                if message_type != "message":
                    await websocket.send_json({"type": "error", "detail": "Unsupported message type"})
                    continue
                now = monotonic()
                while sent_times and now - sent_times[0] >= settings.CHAT_RATE_LIMIT_WINDOW_SECONDS:
                    sent_times.popleft()
                if len(sent_times) >= settings.CHAT_RATE_LIMIT_MESSAGES:
                    await websocket.send_json({"type": "error", "detail": "Message rate limit exceeded"})
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
                    await websocket.send_json({"type": "error", "detail": str(error)})
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
