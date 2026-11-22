import unittest
import tempfile
from datetime import datetime, time, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import working_hours, spontaneous_chat
from app.api.deps import get_current_user, get_audit_repository, get_file_storage
from app.database import get_db
from app.models import EmailStatus, UserRole, SpontaneousChat
from app.schemas.working_hours import WorkingHoursCreate, WorkingHoursUpdate, WorkingHoursBatch, WorkingHoursBatchDelete
from app.services.file_storage import LocalFileStorage
from app.services.notification_service import NotificationService
from app.services.working_hours_service import WorkingHoursService, SpontaneousChatAvailabilityService
from app.services.spontaneous_chat_service import SpontaneousChatService, SpontaneousChatError
from app.services.appointment_service import AppointmentNotFoundError


class WorkingHoursTests(unittest.TestCase):
    def test_batch_rejects_empty_duplicate_invalid_days_and_identifiers(self):
        base = dict(channel='in_person', start_time='09:00', end_time='13:00')
        for days in ([], [0, 0], [-1], [7]):
            with self.assertRaises(ValidationError): WorkingHoursBatch(**base, days_of_week=days)
        self.assertEqual(WorkingHoursBatch(**base, days_of_week=[4, 0, 1]).days_of_week, [0, 1, 4])
        identifier = uuid4()
        with self.assertRaises(ValidationError): WorkingHoursBatchDelete(schedule_ids=[identifier, identifier])

    def test_batch_checks_all_owners_before_modifying_any_row(self):
        repo = Mock()
        user = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL)
        repo.get_owned.side_effect = [SimpleNamespace(id=uuid4()), None]
        request = WorkingHoursBatch(channel='chat', days_of_week=[0, 1], schedule_ids=[uuid4(), uuid4()], start_time='09:00', end_time='13:00')
        with self.assertRaises(AppointmentNotFoundError): WorkingHoursService(repo).save_batch(user, request)
        repo.save.assert_not_called()
        repo.delete.assert_not_called()
    def test_wall_clock_duration_and_owner_validation(self):
        base = dict(day_of_week=0, start_time='09:00', end_time='13:00', channel='in_person')
        for changes in ({'day_of_week': 7}, {'end_time': '08:00'}, {'start_time': '09:00+02:00'},
                        {'slot_duration_min': 241}, {'professional_id': str(uuid4())}, {'channel': 'consultation'}, {'start_time': '09:00:01'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError): WorkingHoursCreate(**(base | changes))
        self.assertEqual(WorkingHoursCreate(**(base | {'channel': 'chat', 'end_time': '09:10'})).channel, 'chat')
        self.assertEqual(WorkingHoursCreate(**(base | {'channel': 'video'})).channel, 'video')
        with self.assertRaises(ValidationError):
            WorkingHoursCreate(**(base | {'channel': 'video', 'end_time': '09:10'}))
        with self.assertRaises(ValidationError): WorkingHoursUpdate(is_active=None)

    def test_update_revalidates_result_and_owned_rows(self):
        repo = Mock()
        user = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL)
        repo.get_owned.return_value = None
        with self.assertRaises(AppointmentNotFoundError): WorkingHoursService(repo).save(user, WorkingHoursUpdate(end_time='10:00'), uuid4())
        repo.get_owned.return_value = SimpleNamespace(id=uuid4(), channel='in_person', day_of_week=0, start_time=time(9), end_time=time(13), slot_duration_min=30, is_active=True)
        with self.assertRaises(ValidationError): WorkingHoursService(repo).save(user, WorkingHoursUpdate(end_time='09:15'), uuid4())
        self.assertEqual(repo.get_owned.return_value.end_time, time(13))

    def test_chat_availability_madrid_hours_boundaries_blocks_and_busy(self):
        hours, professionals = Mock(), Mock()
        professionals.get_professional.return_value = (object(), SimpleNamespace(is_accepting_new_patients=True))
        hours.list.return_value = [SimpleNamespace(is_active=True, day_of_week=0, start_time=time(9), end_time=time(11))]
        hours.session.scalar.return_value = None
        service = SpontaneousChatAvailabilityService(hours, professionals)
        professional_id = uuid4()
        # Monday in July: Madrid UTC+2. At the closing instant access is denied.
        self.assertTrue(service.get(professional_id, datetime(2030, 7, 1, 7, tzinfo=timezone.utc))['available'])
        self.assertEqual(service.get(professional_id, datetime(2030, 7, 1, 9, tzinfo=timezone.utc))['reason'], 'outside_hours')
        hours.session.scalar.side_effect = [uuid4()]
        self.assertEqual(service.get(professional_id, datetime(2030, 7, 1, 7, tzinfo=timezone.utc))['reason'], 'blocked')
        hours.session.scalar.side_effect = [None, uuid4()]
        self.assertEqual(service.get(professional_id, datetime(2030, 7, 1, 7, tzinfo=timezone.utc))['reason'], 'busy')
        professionals.get_professional.return_value = None
        self.assertEqual(service.get(professional_id)['reason'], 'unavailable')


class SpontaneousChatTests(unittest.TestCase):
    def setUp(self):
        self.patient = SimpleNamespace(id=uuid4(), role=UserRole.PATIENT)
        self.professional = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL)
        self.chat = SpontaneousChat(id=uuid4(), patient_id=self.patient.id, professional_id=self.professional.id, status='open')
        self.repo, self.hours, self.availability, self.audits = Mock(), Mock(), Mock(), Mock()
        self.repo.get.return_value = self.chat
        self.repo.existing_message.return_value = None
        self.repo.open_for_pair.return_value = None
        self.repo.save.side_effect = lambda row: row
        self.availability.get.return_value = {'available': True}
        self.directory = tempfile.TemporaryDirectory()
        self.storage = LocalFileStorage(self.directory.name)
        self.service = SpontaneousChatService(self.repo, self.hours, self.availability, self.storage, self.audits)

    def tearDown(self): self.directory.cleanup()

    def test_patient_start_creates_chat_without_assignment_or_appointment(self):
        result = self.service.start(self.patient, self.professional.id)
        self.assertIsInstance(result, SpontaneousChat)
        self.assertEqual(result.patient_id, self.patient.id)
        self.repo.open_for_pair.assert_called_with(self.patient.id, self.professional.id)
        self.assertFalse(hasattr(result, 'appointment_id'))

    def test_existing_open_chat_is_reused_and_only_patient_can_initiate(self):
        self.repo.open_for_pair.return_value = self.chat
        self.assertIs(self.service.start(self.patient, self.professional.id), self.chat)
        self.repo.save.assert_not_called()
        with self.assertRaises(SpontaneousChatError) as error: self.service.start(self.professional, self.professional.id)
        self.assertEqual(error.exception.status, 403)

    def test_availability_enforced_for_start_and_both_senders(self):
        self.availability.get.return_value = {'available': False}
        with self.assertRaises(SpontaneousChatError): self.service.start(self.patient, self.professional.id)
        for user in (self.patient, self.professional):
            with self.assertRaises(SpontaneousChatError) as error: self.service.send(self.chat.id, user, uuid4(), 'Texto')
            self.assertEqual(error.exception.code, 'CHAT_OUTSIDE_AVAILABILITY')
        self.repo.save.assert_not_called()

    def test_third_party_and_admin_cannot_read_send_close_or_download(self):
        for role in (UserRole.PATIENT, UserRole.PROFESSIONAL, UserRole.ADMIN):
            user = SimpleNamespace(id=uuid4(), role=role)
            for operation in (lambda: self.service.owned(self.chat.id, user), lambda: self.service.send(self.chat.id, user, uuid4(), 'Texto'), lambda: self.service.close(self.chat.id, user), lambda: self.service.download(self.chat.id, uuid4(), user)):
                with self.assertRaises(SpontaneousChatError) as error: operation()
                self.assertEqual(error.exception.status, 404)

    def test_plain_text_validation_and_closed_readonly(self):
        for content in ('  ', 'x' * 2001):
            with self.assertRaises(SpontaneousChatError): self.service.send(self.chat.id, self.patient, uuid4(), content)
        self.chat.status = 'closed'
        self.assertIs(self.service.owned(self.chat.id, self.patient), self.chat)
        with self.assertRaises(SpontaneousChatError) as error: self.service.send(self.chat.id, self.patient, uuid4(), 'Mensaje')
        self.assertEqual(error.exception.code, 'CHAT_CLOSED')

    def test_attachments_from_both_roles_are_private_and_idempotent(self):
        for user, mime, data in ((self.patient, 'image/png', b'\x89PNG\r\n\x1a\nfixture'), (self.professional, 'application/pdf', b'%PDF-1.4 fixture')):
            upload = SimpleNamespace(filename='../../imagen.png', content_type=mime, file=BytesIO(data))
            message = self.service.send(self.chat.id, user, uuid4(), '', upload)
            self.assertEqual(message.file_name, 'imagen.png')
            self.assertEqual(self.storage.path_for(message.file_key).read_bytes(), data)
            self.repo.existing_message.return_value = message
            self.availability.get.return_value = {'available': False}
            self.assertIs(self.service.send(self.chat.id, user, message.client_id, '', upload), message)
            self.repo.existing_message.return_value = None
            self.availability.get.return_value = {'available': True}

    def test_new_patient_message_creates_one_in_app_notification_for_the_professional(self):
        notifications = Mock()
        self.service.notifications = NotificationService(notifications)
        client_id = uuid4()
        message = self.service.send(self.chat.id, self.patient, client_id, "Contenido privado")
        self.repo.existing_message.return_value = message
        self.service.send(self.chat.id, self.patient, client_id, "Contenido privado")
        self.repo.existing_message.return_value = None
        self.service.send(self.chat.id, self.professional, uuid4(), "Respuesta")
        notifications.create.assert_called_once()
        alert = notifications.create.call_args.args[0]
        self.assertEqual((alert.recipient_id, alert.entity_id), (self.professional.id, self.chat.id))
        self.assertEqual(alert.type, "spontaneous_chat_message")
        self.assertEqual(alert.email_status, EmailStatus.NOT_APPLICABLE)
        self.assertFalse(alert.email_required)
        self.assertNotIn(message.content, alert.message)

    def test_invalid_empty_large_or_forged_files_rejected(self):
        for mime, data in (('image/png', b'<html>'), ('text/html', b'<html>'), ('application/pdf', b''), ('image/png', b'x' * (10 * 1024 * 1024 + 1))):
            upload = SimpleNamespace(filename='file', content_type=mime, file=BytesIO(data))
            with self.assertRaises(SpontaneousChatError): self.service.send(self.chat.id, self.patient, uuid4(), '', upload)
        self.repo.save.assert_not_called()

    def test_failed_persistence_removes_file(self):
        self.repo.save.side_effect = RuntimeError('database failed')
        upload = SimpleNamespace(filename='a.pdf', content_type='application/pdf', file=BytesIO(b'%PDF-1.4 fixture'))
        with self.assertRaises(RuntimeError): self.service.send(self.chat.id, self.patient, uuid4(), '', upload)
        self.assertEqual(list(self.storage.root.rglob('*.pdf')), [])

    def test_closing_is_allowed_outside_hours_and_idempotent(self):
        self.availability.get.return_value = {'available': False}
        self.service.close(self.chat.id, self.patient)
        self.service.close(self.chat.id, self.professional)
        self.assertEqual(self.chat.status, 'closed')
        self.repo.save.assert_called_once()


class WorkingHoursChatApiTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(working_hours.router)
        self.app.include_router(spontaneous_chat.router)
        self.user = SimpleNamespace(id=uuid4(), role=UserRole.PATIENT)
        self.db = Mock()
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_audit_repository] = lambda: None
        self.app.dependency_overrides[get_file_storage] = lambda: None
        self.client = TestClient(self.app)

    def test_patient_cannot_manage_hours_and_admin_cannot_list_chats(self):
        self.assertEqual(self.client.get('/professionals/me/working-hours').status_code, 403)
        self.user.role = UserRole.ADMIN
        self.assertEqual(self.client.get('/spontaneous-chats').status_code, 403)
        self.db.scalars.assert_not_called()

    def test_bad_cursors_and_unknown_payload_keys_are_rejected(self):
        self.assertEqual(self.client.get(f'/spontaneous-chats/{uuid4()}/messages?before_id={uuid4()}&after_id={uuid4()}').status_code, 422)
        self.assertEqual(self.client.post('/spontaneous-chats', json={'professional_id': str(uuid4()), 'patient_id': str(uuid4())}).status_code, 422)


if __name__ == '__main__': unittest.main()
