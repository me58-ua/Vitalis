import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import chat, ws_chat, spontaneous_chat
from app.api.deps import get_current_user, get_appointment_repository
from app.models import UserRole
from app.schemas.users import AdminUserUpdate
from app.services.chat_service import ChatForbiddenError


class AppointmentInboxTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid4(), role=UserRole.PATIENT)
        self.repo = Mock()
        app = FastAPI()
        app.include_router(chat.router)
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_appointment_repository] = lambda: self.repo
        self.client = TestClient(app)

    def test_inbox_passes_authenticated_owner_and_pagination(self):
        self.repo.list_chat_rooms.return_value = ([dict(appointment_id=uuid4(),
            start_time=datetime.now(timezone.utc), status='confirmed', other_name='Doctor',
            photo_url='https://example.com/photo.jpg')], 21)
        result = self.client.get('/chats/appointments?page=2').json()
        self.repo.list_chat_rooms.assert_called_once_with(self.user.id, 20, 20)
        self.assertEqual(result['chats'][0]['photo_url'], 'https://example.com/photo.jpg')

    def test_admin_cannot_list_private_conversations(self):
        self.user.role = UserRole.ADMIN
        self.assertEqual(self.client.get('/chats/appointments').status_code, 403)
        self.repo.list_chat_rooms.assert_not_called()

    def test_photo_only_accepts_https_and_can_be_removed(self):
        for value in ('javascript:alert(1)', 'data:image/png;base64,abc', 'http://example.com/p.png'):
            with self.assertRaises(ValueError):
                AdminUserUpdate(photo_url=value)
        self.assertIsNone(AdminUserUpdate(photo_url=None).photo_url)


class ChatSocketTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(ws_chat.router)
        self.client = TestClient(app)
        self.user = SimpleNamespace(id=uuid4())
        self.room_id = uuid4()

    def test_socket_rejects_missing_authentication(self):
        with self.assertRaises(WebSocketDisconnect) as error:
            with self.client.websocket_connect(f'/ws/chat/{self.room_id}'):
                pass
        self.assertEqual(error.exception.code, 4401)

    def test_socket_rejects_nonparticipant(self):
        with patch.object(ws_chat, '_authenticate', return_value=self.user), \
             patch.object(ws_chat, 'SessionLocal'), patch.object(ws_chat, 'ChatService') as service:
            service.return_value.get_room_access.side_effect = ChatForbiddenError()
            with self.assertRaises(WebSocketDisconnect) as error:
                with self.client.websocket_connect(f'/ws/chat/{self.room_id}?token=test'):
                    pass
            self.assertEqual(error.exception.code, 4403)

    def test_typing_is_ephemeral_and_invalid_payload_does_not_disconnect(self):
        with patch.object(ws_chat, '_authenticate', return_value=self.user), \
             patch.object(ws_chat, 'SessionLocal'), patch.object(ws_chat, 'ChatService') as service:
            service.return_value.can_write.return_value = True
            with self.client.websocket_connect(f'/ws/chat/{self.room_id}?token=test') as socket:
                socket.send_json([])
                self.assertEqual(socket.receive_json()['code'], 'INVALID_PAYLOAD')
                socket.send_json({'type': 'typing', 'is_typing': True})
                self.assertEqual(socket.receive_json(), {'type': 'typing', 'sender_id': str(self.user.id), 'is_typing': True})
                service.return_value.save_message.assert_not_called()

    def test_spontaneous_socket_is_private_and_broadcasts_typing(self):
        current = Mock()
        current.owned.return_value = SimpleNamespace(status='open', professional_id=uuid4())
        current.availability.get.return_value = {'available': True}
        with patch.object(ws_chat, '_authenticate', return_value=self.user), \
             patch.object(ws_chat, 'SessionLocal'), patch.object(spontaneous_chat, 'service', return_value=current):
            with self.client.websocket_connect(f'/ws/spontaneous-chat/{self.room_id}?token=test') as first:
                with self.client.websocket_connect(f'/ws/spontaneous-chat/{self.room_id}?token=test') as second:
                    first.send_json({'type': 'typing', 'is_typing': True})
                    self.assertEqual(second.receive_json()['sender_id'], str(self.user.id))
                    self.assertEqual(first.receive_json()['type'], 'typing')
            self.assertTrue(current.owned.called)


class SpontaneousCommitTests(unittest.IsolatedAsyncioTestCase):
    async def test_realtime_event_is_sent_only_after_commit(self):
        chat_id, sender_id = uuid4(), uuid4()
        message = SimpleNamespace(id=uuid4(), chat_id=chat_id, sender_id=sender_id, client_id=uuid4(),
            content='Hello', file_name=None, content_type=None, file_size=None, created_at=datetime.now(timezone.utc))
        current = Mock()
        current.send.return_value = message
        events = []
        db = Mock()
        db.commit.side_effect = lambda: events.append('commit')
        async def broadcast(*args):
            events.append('broadcast')
        with patch.object(spontaneous_chat, 'service', return_value=current), \
             patch.object(spontaneous_chat.manager, 'broadcast', side_effect=broadcast):
            await spontaneous_chat.send_message(chat_id, SimpleNamespace(id=sender_id), db, None, None,
                                                message.client_id, 'Hello', None)
        self.assertEqual(events, ['commit', 'broadcast'])

    async def test_failed_commit_does_not_notify_recipient(self):
        chat_id, sender_id = uuid4(), uuid4()
        message = SimpleNamespace(id=uuid4(), chat_id=chat_id, sender_id=sender_id, client_id=uuid4(),
            content='Hello', file_name=None, content_type=None, file_size=None, created_at=datetime.now(timezone.utc))
        current = Mock()
        current.send.return_value = message
        db = Mock()
        db.commit.side_effect = RuntimeError('test database failure')
        with patch.object(spontaneous_chat, 'service', return_value=current), \
             patch.object(spontaneous_chat.manager, 'broadcast', new_callable=AsyncMock) as broadcast:
            with self.assertRaises(RuntimeError):
                await spontaneous_chat.send_message(chat_id, SimpleNamespace(id=sender_id), db, None, None,
                                                    message.client_id, 'Hello', None)
            broadcast.assert_not_called()


if __name__ == '__main__':
    unittest.main()
