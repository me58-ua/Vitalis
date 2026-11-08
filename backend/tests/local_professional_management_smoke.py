"""Read-only check of the running local API and migration. No login or patient writes."""
import json
from urllib.request import urlopen

from sqlalchemy import text
from app.database import engine


def check():
    with urlopen('http://localhost:8000/health', timeout=10) as response:
        assert json.load(response)['status'] == 'ok'
    with urlopen('http://localhost:8000/openapi.json', timeout=10) as response:
        contract = json.load(response)
    for path in ('/professionals/me/time-blocks', '/admin/professionals/profile-changes',
                 '/admin/professionals/{professional_id}/profile-change/approve',
                 '/admin/professionals/{professional_id}/profile-change/reject',
                 '/professionals/me/working-hours', '/spontaneous-chats',
                 '/spontaneous-chats/{chat_id}/messages'):
        assert path in contract['paths'], path
    with engine.connect() as connection:
        revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        assert revision == '0031_spontaneous_chats', revision
        guards = connection.execute(text("SELECT count(*) FROM pg_trigger WHERE tgname IN ('guard_time_block', 'guard_appointment_unavailable', 'guard_weekly_schedule', 'guard_booking_hours') AND NOT tgisinternal")).scalar_one()
        assert guards == 4, guards
    print('Local API healthy; working hours/chat endpoints present; migration 0031 and all four schedule/interval guards installed. No account or patient data modified.')


if __name__ == '__main__':
    check()
