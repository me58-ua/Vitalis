from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from uuid import uuid4

from app.config import settings
from app.models import AuditAction, SpontaneousChat, SpontaneousChatMessage, UserRole
from app.services.audit_service import AuditService


class SpontaneousChatError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


class SpontaneousChatService:
    def __init__(self, repository, hours, availability, storage, audits=None):
        self.repository, self.hours, self.availability, self.storage = repository, hours, availability, storage
        self.audit = AuditService(audits)

    def owned(self, chat_id, user, lock=False):
        chat = self.repository.get(chat_id, lock)
        owner = chat is not None and ((user.role == UserRole.PATIENT and user.id == chat.patient_id)
                                      or (user.role == UserRole.PROFESSIONAL and user.id == chat.professional_id))
        if not owner: raise SpontaneousChatError(404, 'CHAT_NOT_FOUND')
        return chat

    def response(self, chat):
        names = self.repository.names(chat)
        photos = self.repository.photos(chat)
        availability = self.availability.get(chat.professional_id)
        return dict(id=chat.id, patient_id=chat.patient_id, professional_id=chat.professional_id,
                    patient_name=names.get(chat.patient_id, 'Paciente'), professional_name=names.get(chat.professional_id, 'Profesional'),
                    patient_photo_url=photos.get(chat.patient_id), professional_photo_url=photos.get(chat.professional_id),
                    status=chat.status, created_at=chat.created_at, updated_at=chat.updated_at,
                    can_write=chat.status == 'open' and availability['available'], availability=availability)

    def start(self, user, professional_id):
        if user.role != UserRole.PATIENT: raise SpontaneousChatError(403, 'PATIENT_REQUIRED')
        self.hours.lock_owner(professional_id)
        if not self.availability.get(professional_id)['available']:
            raise SpontaneousChatError(409, 'CHAT_OUTSIDE_AVAILABILITY')
        chat = self.repository.open_for_pair(user.id, professional_id)
        if chat is None:
            chat = self.repository.save(SpontaneousChat(patient_id=user.id, professional_id=professional_id, status='open'))
            self.audit.record(user.id, user.role, AuditAction.CREATE, 'spontaneous_chat', chat.id, user.id)
        return chat

    def close(self, chat_id, user):
        chat = self.owned(chat_id, user)
        self.hours.lock_owner(chat.professional_id)
        chat = self.owned(chat_id, user, lock=True)
        if chat.status != 'closed':
            chat.status = 'closed'
            chat.updated_at = datetime.now(timezone.utc)
            self.repository.save(chat)
            self.audit.record(user.id, user.role, AuditAction.UPDATE, 'spontaneous_chat', chat.id, chat.patient_id)
        return chat

    def send(self, chat_id, user, client_id, content, upload=None):
        content = content.strip()
        if len(content) > 2000 or (not content and upload is None): raise SpontaneousChatError(422, 'CHAT_MESSAGE_INVALID')
        chat = self.owned(chat_id, user)
        self.hours.lock_owner(chat.professional_id)
        chat = self.owned(chat_id, user, lock=True)
        previous = self.repository.existing_message(chat.id, user.id, client_id)
        if previous is not None:
            if previous.content != content: raise SpontaneousChatError(409, 'CHAT_REQUEST_CONFLICT')
            return previous
        if chat.status != 'open': raise SpontaneousChatError(403, 'CHAT_CLOSED')
        if not self.availability.get(chat.professional_id)['available']:
            raise SpontaneousChatError(403, 'CHAT_OUTSIDE_AVAILABILITY')
        message = SpontaneousChatMessage(id=uuid4(), chat_id=chat.id, sender_id=user.id, client_id=client_id, content=content,
                                        created_at=datetime.now(timezone.utc))
        file_key = None
        try:
            if upload is not None:
                payload = upload.file.read(settings.SPONTANEOUS_CHAT_MAX_FILE_SIZE_BYTES + 1)
                if not payload or len(payload) > settings.SPONTANEOUS_CHAT_MAX_FILE_SIZE_BYTES:
                    raise SpontaneousChatError(422, 'CHAT_FILE_TOO_LARGE_OR_EMPTY')
                formats = {'application/pdf': ('pdf', b'%PDF-'), 'image/png': ('png', b'\x89PNG\r\n\x1a\n'), 'image/jpeg': ('jpg', b'\xff\xd8\xff')}
                fmt = formats.get(upload.content_type)
                if fmt is None or not payload.startswith(fmt[1]): raise SpontaneousChatError(422, 'CHAT_FILE_TYPE_INVALID')
                file_key = f'spontaneous-chats/{chat.id}/{message.id}.{fmt[0]}'
                self.storage.save(BytesIO(payload), file_key, settings.SPONTANEOUS_CHAT_MAX_FILE_SIZE_BYTES)
                message.file_key, message.content_type, message.file_size = file_key, upload.content_type, len(payload)
                message.file_name = (PurePosixPath((upload.filename or f'adjunto.{fmt[0]}').replace('\\', '/')).name or f'adjunto.{fmt[0]}')[:150]
            chat.updated_at = datetime.now(timezone.utc)
            self.repository.save(message)
            self.repository.save(chat)
            self.audit.record(user.id, user.role, AuditAction.CREATE, 'spontaneous_chat_message', message.id, chat.patient_id)
            return message
        except Exception:
            if file_key: self.storage.path_for(file_key).unlink(missing_ok=True)
            raise

    def download(self, chat_id, message_id, user):
        chat = self.owned(chat_id, user)
        message = self.repository.message(chat.id, message_id)
        if message is None or not message.file_key: raise SpontaneousChatError(404, 'CHAT_FILE_NOT_FOUND')
        path = self.storage.path_for(message.file_key)
        if not path.is_file(): raise SpontaneousChatError(404, 'CHAT_FILE_NOT_FOUND')
        self.audit.record(user.id, user.role, AuditAction.READ, 'spontaneous_chat_attachment', message.id, chat.patient_id)
        return message, path
