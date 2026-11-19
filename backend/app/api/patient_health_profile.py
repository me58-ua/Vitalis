"""Patient-owned health profile and professional sharing controls."""
from uuid import UUID

from fastapi import APIRouter, Response

from app.api.appointments import Appointments
from app.api.patient_health import Audits, CurrentPatient, Profiles, _profile
from app.models import AuditAction
from app.schemas.patient_health_profile import PatientHealthProfileResponse, ProfessionalHealthSharing
from app.services.audit_service import AuditService
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
def get_health_profile(user: CurrentPatient, profiles: Profiles, appointments: Appointments, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {**snapshot(_profile(user, profiles), profiles),
            "appointment_follow_ups": appointments.patient_follow_ups(user.id)}


@router.get('/sharing', response_model=list[ProfessionalHealthSharing])
def list_health_sharing(user: CurrentPatient, appointments: Appointments, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return appointments.list_health_sharing(user.id)


@router.delete('/sharing/{professional_id}', status_code=204)
def revoke_health_sharing(professional_id: UUID, user: CurrentPatient, appointments: Appointments, audits: Audits):
    if appointments.revoke_health_sharing(user.id, professional_id):
        AuditService(audits).record(
            user.id, user.role, AuditAction.UPDATE, "professional_health_sharing", professional_id, user.id,
        )
