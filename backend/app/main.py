from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import appointments, auth, patient_health, prescriptions, professionals, profiles, users

app = FastAPI(title=settings.APP_NAME)

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

@app.get("/health")
def health_check():
    return {"status":"ok"}