"""Exercise schedule migrations and complete chat API against isolated PostgreSQL."""
import importlib.util
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_file_storage
from app.database import Base, engine, get_db
from app.main import app
from app.models import User, UserRole, PatientProfile, ProfessionalProfile, ProfessionalPatient, Appointment, SpontaneousChat, SpontaneousChatMessage
from app.services.file_storage import LocalFileStorage
from app.repositories.privacy_repository import PrivacyRepository


def migration(name):
    spec = importlib.util.spec_from_file_location(name, Path.cwd() / 'alembic/versions' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check():
    overrides = app.dependency_overrides.copy()
    with tempfile.TemporaryDirectory() as directory, engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = 'vitalis_chat_check_' + uuid4().hex
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            Base.metadata.create_all(connection, checkfirst=False)
            assert connection.exec_driver_sql("SELECT current_schema()").scalar() == schema
            connection.exec_driver_sql('DROP TABLE spontaneous_chat_messages')
            connection.exec_driver_sql('DROP TABLE spontaneous_chats')
            connection.exec_driver_sql('ALTER TABLE professional_schedules DROP COLUMN channel CASCADE')
            connection.exec_driver_sql('DROP TABLE professional_time_blocks')
            for column in ('pending_changes', 'change_request_id', 'change_status', 'change_requested_at', 'change_reviewed_at', 'change_reviewed_by', 'change_rejection_reason'):
                connection.exec_driver_sql(f'ALTER TABLE professional_profiles DROP COLUMN {column}')
            m29 = migration('0029_professional_blocks_and_profile_review.py')
            m30 = migration('0030_channel_working_hours.py')
            m31 = migration('0031_spontaneous_chats.py')
            with Operations.context(MigrationContext.configure(connection)):
                m29.upgrade(); m30.upgrade(); m31.upgrade()
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                def user(role, name):
                    row = User(id=uuid4(), role=role, name=name, dni=uuid4().hex[:15], username=uuid4().hex[:20],
                               email=uuid4().hex + '@example.invalid', tel='000000000', birth_date=date(1990, 1, 1), password_hash='test-only', is_active=True)
                    db.add(row); db.flush(); return row
                patient, professional, other, admin = user(UserRole.PATIENT, 'Paciente'), user(UserRole.PROFESSIONAL, 'Médico'), user(UserRole.PATIENT, 'Tercero'), user(UserRole.ADMIN, 'Admin')
                db.add(ProfessionalProfile(user_id=professional.id, specialty='General', license_number='CHECK-CHAT', approval_status='approved'))
                db.add(PatientProfile(user_id=patient.id, share_health_data=True))
                db.commit()
                identities = {row.role: row.id for row in (patient, professional, admin)}
                actor = SimpleNamespace(id=professional.id, role=UserRole.PROFESSIONAL, is_active=True)
                def dependency():
                    try:
                        yield db
                        db.commit()
                    except Exception:
                        db.rollback(); raise
                app.dependency_overrides[get_db] = dependency
                app.dependency_overrides[get_current_user] = lambda: actor
                storage = LocalFileStorage(directory)
                app.dependency_overrides[get_file_storage] = lambda: storage
                client = TestClient(app)
                def call(method, path, status, **kwargs):
                    response = getattr(client, method)(path, **kwargs)
                    assert response.status_code == status, (method, path, response.status_code, response.text)
                    return response.json() if status != 204 else None
                consultation = call('post', '/professionals/me/working-hours', 201, json=dict(channel='consultation', day_of_week=0, start_time='09:00', end_time='12:00', slot_duration_min=30))
                grouped = call('post', '/professionals/me/working-hours/batch', 200, json=dict(channel='consultation', days_of_week=[0, 1, 4], start_time='15:00', end_time='17:00'))
                grouped = call('post', '/professionals/me/working-hours/batch', 200, json=dict(channel='consultation', days_of_week=[0, 2, 4], schedule_ids=[row['id'] for row in grouped], start_time='15:30', end_time='17:00'))
                assert [row['day_of_week'] for row in grouped] == [0, 2, 4]
                before = call('get', '/professionals/me/working-hours', 200)
                call('post', '/professionals/me/working-hours/batch', 409, json=dict(channel='consultation', days_of_week=[1, 4], start_time='16:00', end_time='18:00'))
                assert call('get', '/professionals/me/working-hours', 200) == before, 'Partial batch survived rollback'
                call('post', '/professionals/me/working-hours/batch-delete', 204, json={'schedule_ids': [row['id'] for row in grouped]})
                call('post', '/professionals/me/working-hours', 409, json=dict(channel='consultation', day_of_week=0, start_time='11:00', end_time='13:00'))
                chat_hours = [call('post', '/professionals/me/working-hours', 201, json=dict(channel='chat', day_of_week=day, start_time='00:00', end_time='23:59')) for day in range(7)]
                call('get', '/professionals/me/working-hours', 200)
                actor.id, actor.role = patient.id, UserRole.PATIENT
                call('get', '/professionals/me/working-hours', 403)
                chat = call('post', '/spontaneous-chats', 201, json={'professional_id': str(professional.id)})
                same = call('post', '/spontaneous-chats', 201, json={'professional_id': str(professional.id)})
                assert same['id'] == chat['id']
                endpoint = f"/spontaneous-chats/{chat['id']}"
                request_id = str(uuid4())
                image = b'\x89PNG\r\n\x1a\nfixture'
                message = call('post', endpoint + '/messages', 201, data={'client_id': request_id, 'content': 'Consulta breve'}, files={'file': ('foto.png', image, 'image/png')})
                duplicate = call('post', endpoint + '/messages', 201, data={'client_id': request_id, 'content': 'Consulta breve'}, files={'file': ('foto.png', image, 'image/png')})
                assert duplicate['id'] == message['id']
                actor.id, actor.role = professional.id, UserRole.PROFESSIONAL
                answer = call('post', endpoint + '/messages', 201, data={'client_id': str(uuid4()), 'content': 'Respuesta'}, files={'file': ('instrucciones.pdf', b'%PDF-1.4 fixture', 'application/pdf')})
                response = client.get(endpoint + '/messages/' + message['id'] + '/file')
                assert response.status_code == 200 and response.content == image
                assert response.headers['cache-control'] == 'no-store'
                page = call('get', endpoint + '/messages?limit=1', 200)
                assert len(page['messages']) == 1 and page['has_more']
                earlier = call('get', endpoint + '/messages?before_id=' + page['messages'][0]['id'], 200)
                assert earlier['messages'][0]['id'] == message['id']
                assert db.scalar(select(func.count()).select_from(ProfessionalPatient)) == 0
                assert db.scalar(select(func.count()).select_from(Appointment)) == 0
                assert call('get', '/professionals/me/patients', 200)['total'] == 0
                call('get', '/professionals/patients/' + str(patient.id) + '/health-snapshot', 403)
                actor.id, actor.role = other.id, UserRole.PATIENT
                call('get', endpoint, 404)
                call('get', endpoint + '/messages/' + answer['id'] + '/file', 404)
                actor.id, actor.role = professional.id, UserRole.PROFESSIONAL
                for hours in chat_hours: call('patch', '/professionals/me/working-hours/' + hours['id'], 200, json={'is_active': False})
                call('post', endpoint + '/messages', 403, data={'client_id': str(uuid4()), 'content': 'Fuera de horario'})
                assert not call('get', endpoint, 200)['can_write']
                call('get', endpoint + '/messages', 200)
                call('post', endpoint + '/close', 200)
                call('post', endpoint + '/close', 200)
                # A new booking is restricted to consultations, never chat hours.
                actor.id, actor.role = admin.id, UserRole.ADMIN
                booking = dict(patient_id=str(patient.id), professional_id=str(professional.id), type='video', start_time='2030-07-01T07:00:00Z', end_time='2030-07-01T07:30:00Z')
                call('post', '/admin/appointments', 201, json=booking)
                failure = client.post('/admin/appointments', json=booking | {'start_time': '2030-07-01T13:00:00Z', 'end_time': '2030-07-01T13:30:00Z'})
                assert failure.status_code == 409 and failure.json()['detail'] == 'OUTSIDE_WORKING_HOURS'
                actor.id, actor.role = professional.id, UserRole.PROFESSIONAL
                call('delete', '/professionals/me/working-hours/' + consultation['id'], 204)
                assert db.scalar(select(func.count()).select_from(Appointment)) == 1
                file_keys = PrivacyRepository(db).erase_spontaneous_chats(patient.id)
                assert len(file_keys) == 2
                assert db.scalar(select(func.count()).select_from(SpontaneousChat)) == 0
                assert db.scalar(select(func.count()).select_from(SpontaneousChatMessage)) == 0
                db.commit()
            with Operations.context(MigrationContext.configure(connection)):
                m31.downgrade(); m30.downgrade()
            assert connection.exec_driver_sql("SELECT to_regclass('spontaneous_chats')").scalar() is None
        finally:
            app.dependency_overrides.clear(); app.dependency_overrides.update(overrides)
            transaction.rollback()
    print('PostgreSQL: migrations 0030/0031, independent hours, overlap, ownership, private attachments both ways, idempotence, cursors, outside-hours read-only, close, no patient assignment, booking limits and privacy erasure verified; schema rolled back.')


if __name__ == '__main__': check()
