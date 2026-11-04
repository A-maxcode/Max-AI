from functools import lru_cache
import ipaddress
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Max-AI"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://maxai:change-this-password@localhost:5432/maxai"
    )
    model_server_url: str = "http://127.0.0.1:8080"
    model_name: str = "auto"
    model_system_prompt: str = Field(
        default="You are a helpful, clear, and friendly assistant.",
        max_length=4000,
    )
    model_context_length: int = Field(default=2048, ge=512, le=131072)
    model_max_tokens: int = Field(default=256, ge=1, le=32768)
    model_timeout_seconds: float = Field(default=180, gt=0, le=900)
    model_temperature: float = Field(default=0.7, ge=0, le=2)
    access_token_expire_minutes: int = Field(default=60, ge=5, le=10080)
    allow_registration: bool = True
    frontend_origins: str = "http://localhost:8000"
    session_cookie_name: str = "maxai_session"
    auth_rate_limit: int = Field(default=10, ge=1, le=1000)
    chat_rate_limit: int = Field(default=30, ge=1, le=10000)

    @field_validator("model_server_url")
    @classmethod
    def normalize_model_server_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MODEL_SERVER_URL must use http or https")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("MODEL_SERVER_URL has an invalid port") from exc
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise ValueError("MODEL_SERVER_URL must be an origin without credentials or a path")
        hostname = parsed.hostname.lower()
        if hostname != "model-server":
            try:
                address = ipaddress.ip_address(hostname)
            except ValueError:
                if hostname not in {"localhost", "host.docker.internal"}:
                    raise ValueError("MODEL_SERVER_URL must point to a local or private model server")
            else:
                if not (address.is_private or address.is_loopback):
                    raise ValueError("MODEL_SERVER_URL must point to a private model server")
        return normalized

    @field_validator("database_url")
    @classmethod
    def require_async_database_driver(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(
            ("postgresql+psycopg://", "sqlite+aiosqlite://")
        ):
            raise ValueError("DATABASE_URL must use PostgreSQL/psycopg or SQLite/aiosqlite")
        return value

    @field_validator("frontend_origins")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if not origins or "*" in origins:
            raise ValueError("FRONTEND_ORIGINS must contain explicit origins and cannot include *")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("FRONTEND_ORIGINS entries must be explicit HTTP(S) origins")
        return ",".join(origins)

    @model_validator(mode="after")
    def validate_generation_limits(self) -> "Settings":
        if self.model_max_tokens >= self.model_context_length:
            raise ValueError("MODEL_MAX_TOKENS must be smaller than MODEL_CONTEXT_LENGTH")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return self.frontend_origins.split(",")

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
