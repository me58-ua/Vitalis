import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import admin_reporting
from app.api import professional_management
from app.api import working_hours
from app.api import spontaneous_chat
from app.api import patient_health_profile
from app.ai.onboarding import api as onboarding_chat
from app.api import appointments, auth, chat, habits, health_documents, notifications, patient_health, prescriptions, privacy, professionals, profiles, risk, users, video, ws_chat

from app.database import SessionLocal
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.video_session_repository import VideoSessionRepository
from app.services.notification_dispatcher import NotificationDispatcher
from app.services.video_service import VideoService


def _expire_video_no_shows() -> None:
    with SessionLocal.begin() as db:
        VideoService(AppointmentRepository(db), VideoSessionRepository(db), AuditRepository(db)).expire_professional_no_shows()


async def _video_no_show_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(_expire_video_no_shows)
        except Exception:
            logging.exception("Video no-show check failed")
        await asyncio.sleep(60)


async def _notification_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            NotificationDispatcher(
                NotificationRepository(db),
                UserRepository(db),
                AppointmentRepository(db),
            ).run_once()
            db.commit()
        except Exception:
            logging.exception("Notification dispatcher iteration failed")
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_notification_loop())
    no_show_task = asyncio.create_task(_video_no_show_loop())
    try:
        yield
    finally:
        task.cancel()
        no_show_task.cancel()
        await asyncio.gather(task, no_show_task, return_exceptions=True)

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin_reporting.router)
app.include_router(professional_management.router)
app.include_router(working_hours.router)
app.include_router(spontaneous_chat.router)
app.include_router(users.router)
app.include_router(users.professional_approval_router)
app.include_router(appointments.router)
app.include_router(appointments.patient_router)
app.include_router(profiles.router)
app.include_router(professionals.router)
app.include_router(patient_health.router)
app.include_router(patient_health_profile.router)
app.include_router(onboarding_chat.router)
app.include_router(prescriptions.router)
app.include_router(health_documents.router)
app.include_router(habits.router)
app.include_router(privacy.router)
app.include_router(chat.router)
app.include_router(video.router)
app.include_router(ws_chat.router)
app.include_router(notifications.router)
app.include_router(risk.router)

@app.get("/health")
def health_check():
    return {"status":"ok"}
