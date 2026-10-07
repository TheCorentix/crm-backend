# app/config.py
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ───────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480      # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── App ───────────────────────────────────────────
    APP_NAME: str = "CMR Dashboard API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175,http://127.0.0.1:5500,null"
    FRONTEND_URL: str = "http://localhost:5173"
    # ── Email / SMTP ───────────────────────────────────
    SMTP_HOST:     str = "smtp.gmail.com"
    SMTP_PORT:     int = 587
    SMTP_USER:     str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM:    str = ""

    # ── Loan Form Link ─────────────────────────────────
    FORM_LINK_SECRET:       str = "change-this-to-a-long-random-secret"
    FORM_LINK_EXPIRE_MINUTES: int = 20
    LOAN_FORM_BASE_URL:     str = "https://maneendrakummari.github.io/Loan/"

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()