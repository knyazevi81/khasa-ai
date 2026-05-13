from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecSettings(BaseSettings):
    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: SecretStr = SecretStr("change-me-in-production-please-use-256-bit-key")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Шифрование секретов в БД (API-ключи LLM) ──────────────────────────────
    # Любая произвольная строка — мы её захэшируем в Fernet-ключ.
    # В проде сгенерировать: openssl rand -base64 48
    SECRET_CIPHER_KEY: SecretStr = SecretStr("change-me-cipher-key-min-32-chars-recommended")

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost", "http://localhost:3000"]

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512", "RS256"}
        if v not in allowed:
            raise ValueError(f"JWT algorithm must be one of {allowed}")
        return v


class ProjectSettings(BaseSettings):
    PROJECT_TITLE: str = "khasa"
    PROJECT_DESCRIPTION: str = "Умный ассистент с графом диалога"
    BASE_PATH: str = "/api/v1"


class DataBaseSettings(BaseSettings):
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_PORT: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


class EmailSettings(BaseSettings):
    EMAIL_ENABLED: bool = True
    SMTP_HOST: str = "mailhog"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASS: SecretStr = SecretStr("")
    SMTP_USE_TLS: bool = False
    EMAIL_FROM: str = "khasa <noreply@khasa.local>"

    FRONTEND_URL: str = "http://localhost"
    SUPPORT_EMAIL: str = "admin@khasa.local"


class RegistrationSettings(BaseSettings):
    VERIFICATION_CODE_TTL_MINUTES: int = 15
    VERIFICATION_CODE_LENGTH: int = 6
    VERIFICATION_RESEND_COOLDOWN_SECONDS: int = 60


class LoggingSettings(BaseSettings):
    LOGGING_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    LOGGING_DATEFMT: str = "%Y-%m-%d %H:%M:%S"
    LOG_LEVEL: int = logging.INFO


class Settings(
    DataBaseSettings,
    ProjectSettings,
    EmailSettings,
    RegistrationSettings,
    LoggingSettings,
    SecSettings,
):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
