import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import appointments, auth, chat, habits, health_documents, notifications, patient_health, prescriptions, privacy, professionals, profiles, risk, users, video, ws_chat

from app.database import SessionLocal
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.services.notification_dispatcher import NotificationDispatcher


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
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

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
app.include_router(users.router)
app.include_router(users.professional_approval_router)
app.include_router(appointments.router)
app.include_router(appointments.patient_router)
app.include_router(profiles.router)
app.include_router(professionals.router)
app.include_router(patient_health.router)
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