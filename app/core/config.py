"""Application configuration, loaded from environment variables."""
from functools import lru_cache
from typing import List, Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_NAME: str = "MenuQR API"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://menuqr:menuqr@localhost:5432/menuqr"

    # Security / JWT
    JWT_SECRET: str = "CHANGE_ME_DEV_ONLY_INSECURE_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48
    INVITATION_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    FRONTEND_URL: str = "http://localhost:3000"

    # Redis (rate limiting / cache / jobs)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Email
    EMAIL_PROVIDER: Literal["console", "smtp"] = "console"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAIL_FROM: str = "no-reply@menuqr.local"

    # Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_DIR: str = "./storage"
    S3_BUCKET: str | None = None
    S3_REGION: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_ENDPOINT_URL: str | None = None
    MAX_UPLOAD_SIZE_MB: int = 5

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_REGISTER_PER_MINUTE: int = 3

    # AI Service (Groq LLM)
    GROQ_API_KEY: str | None = None
    AI_SERVICE_API_KEY: str | None = None
    LLM_PRIMARY_MODEL: str = "qwen/qwen3.8-27b"
    LLM_FALLBACK_MODEL: str | None = None
    LLM_TIMEOUT: float = 60.0
    LLM_MAX_OUTPUT_TOKENS: int = 8192
    MAX_CONCURRENT_LLM_CALLS: int = 10

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
