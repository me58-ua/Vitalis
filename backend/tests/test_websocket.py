import asyncio
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.services.auth_service import InvalidAccessTokenError
from app.services.connection_manager import ConnectionManager
from app.models import AppointmentStatus, UserRole


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.payloads = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        self.payloads.append(payload)


class WebSocketTests(unittest.TestCase):
    def test_valid_connection_answers_ping(self):
        user = SimpleNamespace(id=uuid.uuid4(), role=UserRole.PATIENT, is_active=True, name="Patient")
        appointment = SimpleNamespace(
            id=uuid.uuid4(), patient_id=user.id, professional_id=uuid.uuid4(),
            status=AppointmentStatus.CONFIRMED,
            start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        )
        repository = SimpleNamespace(get_appointment=lambda appointment_id: appointment)
        session = SimpleNamespace(close=lambda: None)
        with patch("app.api.ws_chat._authenticate", return_value=user), patch(
            "app.api.ws_chat.SessionLocal", return_value=session
        ), patch("app.api.ws_chat.AppointmentRepository", return_value=repository):
            with TestClient(app).websocket_connect(f"/ws/chat/{appointment.id}?token=valid") as websocket:
                websocket.send_json({"type": "ping"})
                self.assertEqual(websocket.receive_json(), {"type": "pong"})

    def test_missing_token_is_rejected_before_accept(self):
        with self.assertRaises(WebSocketDisconnect) as error:
            with TestClient(app).websocket_connect(f"/ws/chat/{uuid.uuid4()}"):
                pass
        self.assertEqual(error.exception.code, 4401)

    def test_invalid_token_is_rejected_before_accept(self):
        with patch("app.api.ws_chat._authenticate", side_effect=InvalidAccessTokenError):
            with self.assertRaises(WebSocketDisconnect) as error:
                with TestClient(app).websocket_connect(f"/ws/chat/{uuid.uuid4()}?token=invalid"):
                    pass
        self.assertEqual(error.exception.code, 4401)

    def test_connection_manager_broadcasts_and_cleans_connections(self):
        async def exercise():
            manager = ConnectionManager()
            appointment_id = uuid.uuid4()
            first = FakeWebSocket()
            second = FakeWebSocket()
            await manager.connect(appointment_id, first)
            await manager.connect(appointment_id, second)
            await manager.broadcast(appointment_id, {"type": "pong"})
            manager.disconnect(appointment_id, first)
            manager.disconnect(appointment_id, second)
            return appointment_id, first, second, manager

        appointment_id, first, second, manager = asyncio.run(exercise())
        self.assertTrue(first.accepted)
        self.assertEqual(first.payloads, [{"type": "pong"}])
        self.assertEqual(second.payloads, [{"type": "pong"}])
        self.assertNotIn(appointment_id, manager.connections)


if __name__ == "__main__":
    unittest.main()
