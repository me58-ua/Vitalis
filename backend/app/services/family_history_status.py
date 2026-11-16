"""Interpret persisted declarations without treating an empty list as a denial."""
from app.models import FamilyHistoryStatus


def family_history_status(profile, entries):
    if entries:
        return FamilyHistoryStatus.KNOWN_CONDITIONS
    state = getattr(profile, 'onboarding_state', None) or {}
    chat = state.get('chat_v1', {})
    declarations = {answer['question_id']: answer.get('extracted', {}).get('status')
                    for answer in chat.get('answers', [])}
    declarations.update(chat.get('declarations', {}))
    status = declarations.get('family_history') or (state.get('family_history') or {}).get('status')
    if status == 'none':
        return FamilyHistoryStatus.NO_KNOWN_CONDITIONS
    if status == 'unknown':
        return FamilyHistoryStatus.UNKNOWN
    # An old reviewed flag without an explicit declaration is not a denial.
    return FamilyHistoryStatus.NOT_COLLECTED
