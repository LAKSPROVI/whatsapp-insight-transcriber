"""
Configuração central da aplicação WhatsApp Insight Transcriber
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─── API Keys ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.gameron.me"  # Gameron API (protocolo Anthropic, sem /v1)

    # ─── Claude Config ────────────────────────────────────────
    CLAUDE_MODEL: str = "claude-opus-4-6"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.3

    # ─── Multi-Model Strategy ────────────────────────────────────
    CLAUDE_MODEL_CHAT: str = "claude-opus-4-6"         # RAG chat (needs best quality)
    CLAUDE_MODEL_ANALYSIS: str = "claude-sonnet-4-20250514"  # Sentiment, summary, contradictions
    CLAUDE_MODEL_SIMPLE: str = "claude-haiku-4-20250414"     # Classification, formatting, keywords

    # ─── Anthropic Direct Fallback ───────────────────────────────
    ANTHROPIC_DIRECT_URL: str = "https://api.anthropic.com"  # Fallback if proxy is down

    # ─── Data Retention ──────────────────────────────────────────
    DATA_RETENTION_DAYS: int = 90  # Auto-delete conversations after N days (0 = disabled)

    # ─── Prompt Caching ──────────────────────────────────────────
    PROMPT_CACHE_ENABLED: bool = True

    # ─── Agentes ──────────────────────────────────────────────
    MAX_AGENTS: int = 20
    AGENT_TIMEOUT: int = 300  # seconds

    # ─── Upload e Armazenamento ───────────────────────────────
    UPLOAD_DIR: Path = Path("uploads")
    MEDIA_DIR: Path = Path("media")
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_ZIP_FILES: int = 5000
    MAX_ZIP_UNCOMPRESSED_SIZE: int = 1024 * 1024 * 1024  # 1GB

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./whatsapp_insight.db"
    RUN_DB_MIGRATIONS_ON_STARTUP: bool = True

    # ─── App ──────────────────────────────────────────────────
    APP_NAME: str = "WhatsApp Insight Transcriber"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = ""

    # ─── JWT ──────────────────────────────────────────────────
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24h

    # ─── Admin ────────────────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""
    ALLOW_REGISTRATION: bool = False

    # ─── CORS ─────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://transcriber.jurislaw.com.br",
        "https://transcriber.jurislaw.com.br",
    ]

    # ─── Redis / Cache ───────────────────────────────────────────
    REDIS_URL: Optional[str] = "redis://redis:6379/0"
    REDIS_PASSWORD: str = ""
    CACHE_TTL_SECONDS: int = 86400  # 24h
    CACHE_ENABLED: bool = True

    # ─── Logging ─────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json ou console
    LOG_REDACTION_ENABLED: bool = True
    LOG_TRACING_ENABLED: bool = True
    LOG_ERROR_ADVISOR: bool = True

    # ─── Observability ───────────────────────────────────────────
    ENABLE_METRICS: bool = True

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
    if not s.JWT_SECRET_KEY or len(s.JWT_SECRET_KEY) < 32:
        raise ValueError(
            "JWT_SECRET_KEY não configurada ou muito curta (mínimo 32 caracteres)! "
            "Defina a variável de ambiente JWT_SECRET_KEY ou configure no .env"
        )
    if not s.ADMIN_PASSWORD or len(s.ADMIN_PASSWORD) < 8:
        raise ValueError(
            "ADMIN_PASSWORD não configurada ou muito curta (mínimo 8 caracteres)! "
            "Defina a variável de ambiente ADMIN_PASSWORD ou configure no .env"
        )
    if not s.SECRET_KEY or len(s.SECRET_KEY) < 16:
        raise ValueError(
            "SECRET_KEY não configurada ou muito curta (mínimo 16 caracteres)! "
            "Defina a variável de ambiente SECRET_KEY ou configure no .env"
        )


settings = Settings()
