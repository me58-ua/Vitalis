from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "vitaLis"
    ENV: str = "dev"
    FRONTEND_URL: str = "http://localhost:3000"

    DATABASE_URL: str

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 2525
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    AI_API_URL: str = ""
    AI_API_KEY: str = ""
    FILE_STORAGE_PATH: str = "storage"
    PRESCRIPTION_EMISSION_WINDOW_HOURS: int = 8
    PRESCRIPTION_MAX_SIZE_BYTES: int = 10 * 1024 * 1024
    HEALTH_DOCUMENT_MAX_SIZE_BYTES: int = 10 * 1024 * 1024
    CHAT_WRITE_WINDOW_HOURS: int = 24
    CHAT_MESSAGE_MAX_LENGTH: int = 2000
    CHAT_CONNECTION_IDLE_TIMEOUT_SECONDS: int = 60
    CHAT_RATE_LIMIT_MESSAGES: int = 10
    CHAT_RATE_LIMIT_WINDOW_SECONDS: int = 5
    JITSI_DOMAIN: str = ""
    JITSI_XMPP_DOMAIN: str = "meet.jitsi"
    JITSI_APP_ID: str = ""
    JITSI_APP_SECRET: str = ""
    JITSI_TOKEN_TTL_SECONDS: int = 3600
    VIDEO_JOIN_EARLY_MINUTES: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
