import asyncio
from collections import deque
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
from app.services.auth_service import AuthService, InvalidAccessTokenError
from app.services.chat_service import ChatForbiddenError, ChatNotFoundError, ChatService, ChatValidationError
from app.services.connection_manager import ConnectionManager

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

    db = SessionLocal()
    appointments = AppointmentRepository(db)
    try:
        service = ChatService(appointments, ChatMessageRepository(db))
        try:
            service.get_room_access(appointment_id, user)
        except ChatNotFoundError:
            await websocket.close(code=4404)
            return
        except ChatForbiddenError:
            await websocket.close(code=4403)
            return

        await manager.connect(appointment_id, websocket)
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
                    message = service.save_message(appointment_id, user, str(payload.get("content", "")))
                except (ChatForbiddenError, ChatValidationError) as error:
                    await websocket.send_json({"type": "error", "detail": str(error)})
                    continue
                sent_times.append(now)
                await db.commit()
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
        db.close()
