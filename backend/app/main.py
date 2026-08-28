from fastapi import fastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import auth, users, appointments, consultations, chat_ws, video

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
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(appointments.router, prefix="/appointments", tags=["appointments"])

@app.get("/health")
def  health_check():
    return {"status":"ok"}