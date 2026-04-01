"""
Configuração central da aplicação WhatsApp Insight Transcriber
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ─── API Keys ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(default="sk-user-a5ed66b337aabf59e99500dc2fbcc32e", env="ANTHROPIC_API_KEY")
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

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./whatsapp_insight.db",
        env="DATABASE_URL"
    )

    # ─── App ──────────────────────────────────────────────────
    APP_NAME: str = "WhatsApp Insight Transcriber"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=True, env="DEBUG")
    SECRET_KEY: str = Field(default="change-me-in-production-super-secret-key", env="SECRET_KEY")

    # ─── CORS ─────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://transcriber.jurislaw.com.br", "https://transcriber.jurislaw.com.br"],
        env="ALLOWED_ORIGINS"
    )

    # ─── Redis (opcional, para queue distribuída) ─────────────
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def model_post_init(self, __context):
        # Criar diretórios se não existirem
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.MEDIA_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
