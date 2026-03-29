"""
SARC360 ERP - Configuration
شركة سما الروابي للمقاولات - الخبر
"""

from decimal import Decimal
from typing import Literal

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "SARC360 ERP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://sarc360:sarc360pass@localhost:5432/sarc360"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security / JWT ───────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Saudi Business Constants ─────────────────────────────────────────────
    KSA_VAT_RATE: Decimal = Decimal("0.15")          # 15% VAT
    GOSI_EMPLOYER_RATE: Decimal = Decimal("0.10")    # 10% employer GOSI
    GOSI_EMPLOYEE_RATE: Decimal = Decimal("0.09")    # 9%  employee GOSI (Saudi nationals)
    DEFAULT_CURRENCY: str = "SAR"
    DEFAULT_TIMEZONE: str = "Asia/Riyadh"

    # ── ZATCA Phase 2 ────────────────────────────────────────────────────────
    ZATCA_ENV: Literal["sandbox", "production"] = "sandbox"
    ZATCA_CSID: str = ""
    ZATCA_PRIVATE_KEY_PEM: str = ""
    ZATCA_API_BASE_URL: str = "https://gw-apic-gov.gazt.gov.sa/e-invoicing/core"

    # ── WPS / Mudad ──────────────────────────────────────────────────────────
    MUDAD_API_KEY: str = ""

    # ── Notifications ────────────────────────────────────────────────────────
    WHATSAPP_API_KEY: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Include localhost ports used by the HTML frontend + Next.js dev server
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:5500",   # VS Code Live Server
        "http://127.0.0.1:8080",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
