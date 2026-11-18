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
            for column in ('years_experience', 'languages', 'email_notifications_enabled'):
                connection.exec_driver_sql(f'ALTER TABLE professional_profiles DROP COLUMN {column}')
            for column in ('pending_changes', 'change_request_id', 'change_status', 'change_requested_at', 'change_reviewed_at', 'change_reviewed_by', 'change_rejection_reason'):
                connection.exec_driver_sql(f'ALTER TABLE professional_profiles DROP COLUMN {column}')
            m29 = migration('0029_professional_blocks_and_profile_review.py')
            m30 = migration('0030_channel_working_hours.py')
            m31 = migration('0031_spontaneous_chats.py')
            m32 = migration('0032_professional_profile_details.py')
            m38 = migration('0038_modality_working_hours.py')
            with Operations.context(MigrationContext.configure(connection)):
                m29.upgrade(); m30.upgrade(); m31.upgrade(); m32.upgrade()
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                def user(role, name):
                    row = User(id=uuid4(), role=role, name=name, dni=uuid4().hex[:15], username=uuid4().hex[:20],
                               email=uuid4().hex + '@example.invalid', tel='000000000', birth_date=date(1990, 1, 1), password_hash='test-only', is_active=True)
                    db.add(row); db.flush(); return row
                patient, professional, other, admin = user(UserRole.PATIENT, 'Paciente'), user(UserRole.PROFESSIONAL, 'Médico'), user(UserRole.PATIENT, 'Tercero'), user(UserRole.ADMIN, 'Admin')
                db.add(ProfessionalProfile(user_id=professional.id, specialty='General', license_number='CHECK-CHAT', approval_status='approved'))
                db.add(PatientProfile(user_id=patient.id, share_health_data=True))
                db.commit()
                connection.exec_driver_sql(
                    "INSERT INTO professional_schedules (professional_id, day_of_week, start_time, end_time, is_active) "
                    "VALUES (%s, 6, '09:00', '12:00', false)", (professional.id,),
                )
                with Operations.context(MigrationContext.configure(connection)):
                    m38.upgrade()
                assert connection.exec_driver_sql(
                    "SELECT channel FROM professional_schedules WHERE day_of_week=6 ORDER BY channel"
                ).scalars().all() == ['in_person', 'video']
                identities = {row.role: row.id for row in (patient, professional, admin)}
                actor = SimpleNamespace(id=professional.id, role=UserRole.PROFESSIONAL, is_active=True, name=professional.name)
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
                public_profile = '/professionals/' + str(professional.id)
                assert call('get', public_profile, 200)['languages'] == []
                assert call('get', '/professionals/me/notification-settings', 200)['email_notifications_enabled'] is True
                call('patch', '/professionals/me/notification-settings', 200, json={'email_notifications_enabled': False})
                db.expire_all()
                assert call('get', '/professionals/me/notification-settings', 200)['email_notifications_enabled'] is False
                change = call('patch', '/professionals/me/profile', 200, json={'languages': ['Español', ' Inglés '], 'years_experience': 15, 'bio': 'Consulta preventiva', 'practice_phone': '123456789'})
                assert change['languages'] == [] and change['pending_changes']['languages'] == ['Español', 'Inglés']
                assert call('get', public_profile, 200)['years_experience'] is None
                actor.id, actor.role = patient.id, UserRole.PATIENT
                call('get', '/professionals/me/notification-settings', 403)
                call('patch', '/professionals/me/profile', 403, json={'languages': ['Francés']})
                actor.id, actor.role = admin.id, UserRole.ADMIN
                call('post', f'/admin/professionals/{professional.id}/profile-change/approve', 200, json={'request_id': change['change_request_id']})
                published = call('get', public_profile, 200)
                assert published['languages'] == ['Español', 'Inglés'] and published['years_experience'] == 15
                assert published['bio'] == 'Consulta preventiva' and published['practice_phone'] == '123456789'
                assert 'email_notifications_enabled' not in published and 'pending_changes' not in published
                directory = call('get', '/professionals', 200)['professionals'][0]
                assert directory['languages'] == published['languages'] and directory['years_experience'] == 15
                actor.id, actor.role = professional.id, UserRole.PROFESSIONAL
                video = call('post', '/professionals/me/working-hours', 201, json=dict(channel='video', day_of_week=0, start_time='09:00', end_time='12:00', slot_duration_min=30))
                call('post', '/professionals/me/working-hours', 201, json=dict(channel='in_person', day_of_week=0, start_time='14:00', end_time='15:00'))
                grouped = call('post', '/professionals/me/working-hours/batch', 200, json=dict(channel='in_person', days_of_week=[0, 1, 4], start_time='15:00', end_time='17:00'))
                grouped = call('post', '/professionals/me/working-hours/batch', 200, json=dict(channel='in_person', days_of_week=[0, 2, 4], schedule_ids=[row['id'] for row in grouped], start_time='15:30', end_time='17:00'))
                assert [row['day_of_week'] for row in grouped] == [0, 2, 4]
                before = call('get', '/professionals/me/working-hours', 200)
                call('post', '/professionals/me/working-hours/batch', 409, json=dict(channel='in_person', days_of_week=[1, 4], start_time='16:00', end_time='18:00'))
                assert call('get', '/professionals/me/working-hours', 200) == before, 'Partial batch survived rollback'
                call('post', '/professionals/me/working-hours/batch-delete', 204, json={'schedule_ids': [row['id'] for row in grouped]})
                call('post', '/professionals/me/working-hours', 409, json=dict(channel='video', day_of_week=0, start_time='11:00', end_time='13:00'))
                chat_hours = [call('post', '/professionals/me/working-hours', 201, json=dict(channel='chat', day_of_week=day, start_time='00:00', end_time='23:59')) for day in range(7)]
                call('get', '/professionals/me/working-hours', 200)
                actor.id, actor.role = patient.id, UserRole.PATIENT
                call('get', '/professionals/me/working-hours', 403)
                availability = public_profile + '/availability'
                for modality, hour, count in [('video', 9, 6), ('in_person', 14, 2)]:
                    slots = call('get', availability, 200, params={'requested_date': '2030-07-01', 'appointment_type': modality})['slots']
                    assert len(slots) == count and slots[0]['start_time'][11:13] == str(hour).zfill(2)
                    assert all(slot['type'] == modality for slot in slots)
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
                booked = call('post', '/admin/appointments', 201, json=booking)
                call('patch', '/admin/appointments/' + booked['id'], 409, json={'type': 'in_person'})
                failure = client.post('/admin/appointments', json=booking | {'start_time': '2030-07-01T12:00:00Z', 'end_time': '2030-07-01T12:30:00Z'})
                assert failure.status_code == 409 and failure.json()['detail'] == 'OUTSIDE_WORKING_HOURS'
                actor.id, actor.role = professional.id, UserRole.PROFESSIONAL
                call('delete', '/professionals/me/working-hours/' + video['id'], 204)
                assert db.scalar(select(func.count()).select_from(Appointment)) == 1
                file_keys = PrivacyRepository(db).erase_spontaneous_chats(patient.id)
                assert len(file_keys) == 2
                assert db.scalar(select(func.count()).select_from(SpontaneousChat)) == 0
                assert db.scalar(select(func.count()).select_from(SpontaneousChatMessage)) == 0
                db.commit()
            with Operations.context(MigrationContext.configure(connection)):
                m38.downgrade(); m32.downgrade(); m31.downgrade(); m30.downgrade()
            assert connection.exec_driver_sql('SELECT to_regclass(%s)', (f'{schema}.spontaneous_chats',)).scalar() is None
        finally:
            app.dependency_overrides.clear(); app.dependency_overrides.update(overrides)
            transaction.rollback()
    print('PostgreSQL: schedule migrations, modality-specific slots and booking constraints, profile approval, chat and privacy checks passed; schema rolled back.')


if __name__ == '__main__': check()
