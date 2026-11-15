from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import get_current_patient, get_profile_repository, DbSession, get_notification_service
from app.ai.onboarding.gemini import AIUnavailable
from app.models import PatientProfile, User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.risk_repository import RiskRepository
from app.repositories.risk_snapshot_repository import RiskSnapshotRepository
from app.schemas.onboarding_chat import ChatAnswer, ChatConfirmation, ChatConsent, OnboardingChatState
from app.services.notification_service import NotificationService
from app.ai.onboarding.service import ChatConflict, OnboardingChatService
from app.services.risk_service import RiskService

router = APIRouter(prefix="/onboarding/chat", tags=["onboarding-chat"])
CurrentPatient = Annotated[User, Depends(get_current_patient)]
Profiles = Annotated[ProfileRepository, Depends(get_profile_repository)]
Notifications = Annotated[NotificationService, Depends(get_notification_service)]


def profile_for(user, profiles, lock=False):
    query = select(PatientProfile).where(PatientProfile.user_id == user.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    profile = profiles.session.scalar(query)
    if profile is None:
        raise HTTPException(status_code=404, detail="No se ha encontrado tu perfil de paciente.")
    return profile


def run(action):
    try:
        return action()
    except AIUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except ChatConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("", response_model=OnboardingChatState)
def chat_state(user: CurrentPatient, profiles: Profiles):
    return OnboardingChatService(profiles).state(profile_for(user, profiles))


@router.post("/consent", response_model=OnboardingChatState)
def chat_consent(data: ChatConsent, user: CurrentPatient, profiles: Profiles):
    return run(lambda: OnboardingChatService(profiles).consent(profile_for(user, profiles, True), data.accepted))


@router.post("/answer", response_model=OnboardingChatState)
def chat_answer(data: ChatAnswer, user: CurrentPatient, profiles: Profiles):
    return run(lambda: OnboardingChatService(profiles).answer(profile_for(user, profiles, True), data.question_id, data.message))


@router.post("/confirm", response_model=OnboardingChatState)
def chat_confirm(data: ChatConfirmation, user: CurrentPatient, profiles: Profiles, db: DbSession, notifications: Notifications):
    service = OnboardingChatService(profiles, RiskService(RiskRepository(db), RiskSnapshotRepository(db), notifications))
    return run(lambda: service.confirm(profile_for(user, profiles, True), data.draft_id, data.confirmed))
