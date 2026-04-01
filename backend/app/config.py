"""
Configuração central da aplicação WhatsApp Insight Transcriber
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # ─── API Keys ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(default="", env="ANTHROPIC_API_KEY")
    ANTHROPIC_BASE_URL: str = Field(
        default="https://api.gameron.me",  # Gameron API (protocolo Anthropic, sem /v1)
        env="ANTHROPIC_BASE_URL"
    )

    # ─── Claude Config ────────────────────────────────────────
    CLAUDE_MODEL: str = Field(default="claude-opus-4-6", env="CLAUDE_MODEL")
    MAX_TOKENS: int = Field(default=4096, env="MAX_TOKENS")
    TEMPERATURE: float = Field(default=0.3, env="TEMPERATURE")

    # ─── Agentes ──────────────────────────────────────────────
    MAX_AGENTS: int = Field(default=20, env="MAX_AGENTS")
    AGENT_TIMEOUT: int = Field(default=300, env="AGENT_TIMEOUT")  # seconds

    # ─── Upload e Armazenamento ───────────────────────────────
    UPLOAD_DIR: Path = Field(default=Path("uploads"), env="UPLOAD_DIR")
    MEDIA_DIR: Path = Field(default=Path("media"), env="MEDIA_DIR")
    MAX_UPLOAD_SIZE: int = Field(default=500 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 500MB
    MAX_UPLOAD_SIZE_MB: int = Field(default=100, env="MAX_UPLOAD_SIZE_MB")
    MAX_ZIP_FILES: int = Field(default=5000, env="MAX_ZIP_FILES")
    MAX_ZIP_UNCOMPRESSED_SIZE: int = Field(
        default=1024 * 1024 * 1024,  # 1GB
        env="MAX_ZIP_UNCOMPRESSED_SIZE"
    )

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./whatsapp_insight.db",
        env="DATABASE_URL"
    )

    # ─── App ──────────────────────────────────────────────────
    APP_NAME: str = "WhatsApp Insight Transcriber"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    SECRET_KEY: str = Field(default="change-me-in-production-super-secret-key", env="SECRET_KEY")

    # ─── JWT ──────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="", env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_MINUTES: int = Field(default=1440, env="JWT_EXPIRATION_MINUTES")  # 24h

    # ─── Admin ────────────────────────────────────────────────
    ADMIN_USERNAME: str = Field(default="admin", env="ADMIN_USERNAME")
    ADMIN_PASSWORD: str = Field(default="", env="ADMIN_PASSWORD")
    ALLOW_REGISTRATION: bool = Field(default=False, env="ALLOW_REGISTRATION")

    # ─── CORS ─────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://transcriber.jurislaw.com.br", "https://transcriber.jurislaw.com.br"],
        env="ALLOWED_ORIGINS"
    )

    # ─── Redis (opcional, para queue distribuída) ─────────────
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    def model_post_init(self, __context):
        # Criar diretórios se não existirem
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def validate_settings(s: "Settings") -> None:
    """Valida configurações críticas no startup. Raise ValueError se inválido."""
    if not s.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY não configurada! "
            "Defina a variável de ambiente ANTHROPIC_API_KEY ou configure no .env"
        )
    if not s.JWT_SECRET_KEY:
        raise ValueError(
            "JWT_SECRET_KEY não configurada! "
            "Defina a variável de ambiente JWT_SECRET_KEY ou configure no .env"
        )
    if not s.ADMIN_PASSWORD:
        raise ValueError(
            "ADMIN_PASSWORD não configurada! "
            "Defina a variável de ambiente ADMIN_PASSWORD ou configure no .env"
        )


settings = Settings()
