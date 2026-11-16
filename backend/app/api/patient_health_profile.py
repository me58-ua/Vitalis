"""Read-only patient-owned health profile. Changes go through the AI conversation."""
from fastapi import APIRouter

from app.api.patient_health import CurrentPatient, Profiles, _profile
from app.schemas.patient_health_profile import PatientHealthProfileResponse
from app.services.family_history_status import family_history_status


router = APIRouter(prefix='/patients/me/health-profile', tags=['patient-health-profile'])


def snapshot(profile, profiles):
    chat = (profile.onboarding_state or {}).get('chat_v1') or {}
    declarations = {a['question_id']: a.get('extracted', {}).get('status', 'unknown') for a in chat.get('answers', [])}
    declarations.update(chat.get('declarations', {}))
    records = profiles.list_health_records(profile.id)
    return {'profile': profile, **records,
            'family_history_status': family_history_status(profile, records.get('family_history_entries', [])),
            'alcohol_logs': profiles.list_alcohol_logs(profile.id),
            'alcohol_current': (profile.onboarding_state or {}).get('alcohol_current'),
            'declarations': declarations, 'onboarding_stage': chat.get('stage', 'consent')}


@router.get('', response_model=PatientHealthProfileResponse)
def get_health_profile(user: CurrentPatient, profiles: Profiles):
    return snapshot(_profile(user, profiles), profiles)
