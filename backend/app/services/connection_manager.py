from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, appointment_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[appointment_id].add(websocket)

    def disconnect(self, appointment_id: UUID, websocket: WebSocket) -> None:
        room = self.connections.get(appointment_id)
        if room is None:
            return
        room.discard(websocket)
        if not room:
            self.connections.pop(appointment_id, None)

    async def broadcast(self, appointment_id: UUID, payload: dict) -> None:
        for websocket in tuple(self.connections.get(appointment_id, ())):
            await websocket.send_json(payload)
